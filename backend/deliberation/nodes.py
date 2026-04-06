"""LangGraph node functions for the Friction deliberation graph.

Each node receives the full ``DeliberationState`` and returns a *partial*
dict of only the keys it wants to update — LangGraph merges it back.

External dependency (the LLM client) is stored in a module-level variable
that ``DeliberationEngine`` sets before invoking the graph.  This avoids
serialisation issues and keeps the state dict JSON-safe.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.deliberation.prompts import (
    CHALLENGE_PROMPT,
    COGNITIVE_FORCING_PROMPT,
    INITIAL_PROBE_PROMPT,
    PREMORTEM_PROMPT,
    REDIRECT_PROMPT,
    REQUIREMENTS_PROMPT,
    ROUTE_PROMPT,
    SUMMARY_PROMPT,
)
from backend.deliberation.state import DeliberationPhase, DeliberationState
from backend.services.llm import LLMClient
from backend.services.web_search import (
    build_search_query,
    format_search_results,
    should_search,
    web_search,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level LLM handle — set by DeliberationEngine before each invocation
# ---------------------------------------------------------------------------
_llm: LLMClient | None = None


def set_llm_client(client: LLMClient) -> None:
    """Called by the engine to inject the shared LLM client."""
    global _llm
    _llm = client


def _get_llm() -> LLMClient:
    if _llm is None:
        raise RuntimeError(
            "LLM client not initialised — call set_llm_client() first."
        )
    return _llm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_conversation(messages: list[dict]) -> str:
    """Turn the message list into a readable transcript for prompt injection."""
    if not messages:
        return "(No conversation yet.)"
    lines: list[str] = []
    for msg in messages:
        role = msg["role"].upper()
        lines.append(f"[{role}]: {msg['content']}")
    return "\n\n".join(lines)


def _format_codebase(summary: str) -> str:
    if not summary:
        return ""
    return f"Existing codebase context:\n{summary}"


def _fill_prompt(template: str, state: DeliberationState, **extra: str) -> str:
    """Fill common placeholders shared by all phase prompts."""
    # Provide a default empty string for web_search_results if not in extra
    # and the template contains the placeholder
    if "web_search_results" not in extra:
        extra["web_search_results"] = ""
    return template.format(
        user_idea=state["idea"],
        conversation_history=_format_conversation(state["messages"]),
        codebase_summary=_format_codebase(state.get("codebase_summary", "")),
        **extra,
    )


async def _run_phase_node(
    state: DeliberationState,
    prompt_template: str,
    temperature: float = 0.7,
    max_tokens: int = 600,
) -> dict[str, Any]:
    """Generic helper: fill the prompt, call the LLM, append the response.

    Optionally performs a web search before calling the LLM when the
    conversation context suggests it would add value.
    """
    llm = _get_llm()
    phase = state.get("phase", "probing")

    # --- Decide whether to web-search ---
    web_searched = False
    search_results_text = ""

    # Get the latest user message (or the idea if first turn)
    user_messages = [m for m in state["messages"] if m["role"] == "user"]
    latest_user_text = user_messages[-1]["content"] if user_messages else state["idea"]

    if should_search(latest_user_text, phase, state["idea"]):
        query = build_search_query(latest_user_text, state["idea"], phase)
        results = await web_search(query, num_results=5)
        if results:
            search_results_text = format_search_results(results)
            web_searched = True
            logger.info("Web search enriched phase=%s query=%r (%d results)", phase, query, len(results))

    system_prompt = _fill_prompt(
        prompt_template, state, web_search_results=search_results_text,
    )

    # Build message list for LLM (just the raw conversation)
    llm_messages = [
        {"role": m["role"] if m["role"] == "user" else "assistant", "content": m["content"]}
        for m in state["messages"]
    ]
    # If the conversation is empty (first turn), add a synthetic user
    # message so the LLM has something to respond to.
    if not llm_messages:
        llm_messages = [{"role": "user", "content": state["idea"]}]

    response = await llm.chat_completion(
        messages=llm_messages,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    updated_messages = list(state["messages"]) + [
        {"role": "friction", "content": response}
    ]

    return {
        "messages": updated_messages,
        "turn_count": state["turn_count"] + 1,
        "phase_turn_count": state["phase_turn_count"] + 1,
        "web_searched": web_searched,
    }


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

async def probe_node(state: DeliberationState) -> dict[str, Any]:
    """Phase 1 — ask probing questions about the idea."""
    result = await _run_phase_node(state, INITIAL_PROBE_PROMPT)
    result["phase"] = DeliberationPhase.PROBING.value
    return result


async def requirements_node(state: DeliberationState) -> dict[str, Any]:
    """Phase 2 — elicit concrete requirements (scope, tech stack, integrations)."""
    result = await _run_phase_node(state, REQUIREMENTS_PROMPT)
    result["phase"] = DeliberationPhase.REQUIREMENTS.value
    return result


async def cognitive_forcing_node(state: DeliberationState) -> dict[str, Any]:
    """Phase 2 — ask the user to rate confidence before revealing AI scores."""
    result = await _run_phase_node(state, COGNITIVE_FORCING_PROMPT)
    result["phase"] = DeliberationPhase.COGNITIVE_FORCING.value
    return result


async def challenge_node(state: DeliberationState) -> dict[str, Any]:
    """Phase 3 — devil's advocate pushback on assumptions."""
    result = await _run_phase_node(state, CHALLENGE_PROMPT, temperature=0.8)
    result["phase"] = DeliberationPhase.CHALLENGE.value
    return result


async def premortem_node(state: DeliberationState) -> dict[str, Any]:
    """Phase 4 — generate concrete failure scenarios."""
    result = await _run_phase_node(state, PREMORTEM_PROMPT)
    result["phase"] = DeliberationPhase.PREMORTEM.value
    return result


async def summarize_node(state: DeliberationState) -> dict[str, Any]:
    """Phase 5 — produce structured JSON summary and complete deliberation."""
    llm = _get_llm()
    system_prompt = _fill_prompt(SUMMARY_PROMPT, state)

    llm_messages = [
        {"role": m["role"] if m["role"] == "user" else "assistant", "content": m["content"]}
        for m in state["messages"]
    ]
    if not llm_messages:
        llm_messages = [{"role": "user", "content": state["idea"]}]

    try:
        summary = await llm.structured_output(
            messages=llm_messages,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2000,
        )
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Structured output failed, falling back to text: %s", exc)
        raw = await llm.chat_completion(
            messages=llm_messages,
            system_prompt=system_prompt,
            temperature=0.3,
        )
        summary = {"raw_summary": raw}

    # Extract fields from summary into state
    key_insights = summary.get("key_insights", state.get("key_insights", []))
    risks_raw = summary.get("top_risks", [])
    risks = [
        r["risk"] if isinstance(r, dict) else str(r)
        for r in risks_raw
    ]
    refined_idea = summary.get("refined_idea", state.get("refined_idea", state["idea"]))

    # Append a human-readable summary message for the conversation
    summary_text = _format_summary_for_display(summary)
    updated_messages = list(state["messages"]) + [
        {"role": "friction", "content": summary_text}
    ]

    return {
        "messages": updated_messages,
        "turn_count": state["turn_count"] + 1,
        "phase_turn_count": 1,
        "phase": DeliberationPhase.COMPLETE.value,
        "key_insights": key_insights,
        "risks": risks,
        "refined_idea": refined_idea,
        "should_complete": True,
    }


def _format_summary_for_display(summary: dict) -> str:
    """Turn the structured summary dict into a readable message."""
    parts: list[str] = []

    if refined := summary.get("refined_idea"):
        parts.append(f"REFINED IDEA\n{refined}")

    if insights := summary.get("key_insights"):
        parts.append("KEY INSIGHTS\n" + "\n".join(f"- {i}" for i in insights))

    if risks := summary.get("top_risks"):
        risk_lines: list[str] = []
        for r in risks:
            if isinstance(r, dict):
                sev = r.get("severity", "?")
                risk_lines.append(
                    f"- [{sev.upper()}] {r.get('risk', '?')} — Mitigation: {r.get('mitigation', 'none')}"
                )
            else:
                risk_lines.append(f"- {r}")
        parts.append("TOP RISKS\n" + "\n".join(risk_lines))

    if scope := summary.get("recommended_scope"):
        parts.append(f"RECOMMENDED SCOPE\n{scope}")

    if cuts := summary.get("what_to_cut"):
        parts.append("CUT FROM V1\n" + "\n".join(f"- {c}" for c in cuts))

    if stack := summary.get("suggested_tech_stack"):
        stack_lines = [f"- {k}: {v}" for k, v in stack.items() if v]
        parts.append("SUGGESTED TECH STACK\n" + "\n".join(stack_lines))

    if delta := summary.get("confidence_delta"):
        if commentary := delta.get("commentary"):
            parts.append(f"CONFIDENCE NOTES\n{commentary}")

    return "\n\n".join(parts) if parts else json.dumps(summary, indent=2)


async def process_user_input_node(state: DeliberationState) -> dict[str, Any]:
    """Pass-through node — the user message is already in state.

    Routing decisions happen in ``route_deliberation``, not here.
    This node exists so the graph has a consistent entry point.
    """
    return {}


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

_PHASE_ORDER = [
    DeliberationPhase.PROBING,
    DeliberationPhase.REQUIREMENTS,
    DeliberationPhase.COGNITIVE_FORCING,
    DeliberationPhase.CHALLENGE,
    DeliberationPhase.PREMORTEM,
    DeliberationPhase.SUMMARY,
    DeliberationPhase.COMPLETE,
]

_PHASE_MAX_TURNS: dict[str, int] = {
    DeliberationPhase.PROBING.value: 1,
    DeliberationPhase.REQUIREMENTS.value: 1,
    DeliberationPhase.COGNITIVE_FORCING.value: 1,
    DeliberationPhase.CHALLENGE.value: 1,
    DeliberationPhase.PREMORTEM.value: 1,
    DeliberationPhase.SUMMARY.value: 1,
}


def _next_phase(current: str) -> str:
    """Return the phase that follows *current* in the normal flow."""
    for i, phase in enumerate(_PHASE_ORDER):
        if phase.value == current and i + 1 < len(_PHASE_ORDER):
            return _PHASE_ORDER[i + 1].value
    return DeliberationPhase.SUMMARY.value


_SKIP_KEYWORDS = {
    "done", "skip", "move on", "let's wrap up", "wrap up",
    "finish", "next", "let's move on", "summarize", "summary",
}


def _user_wants_to_skip(messages: list[dict]) -> bool:
    """Check if the latest user message signals they want to advance."""
    if not messages:
        return False
    last_user_msgs = [m for m in messages if m["role"] == "user"]
    if not last_user_msgs:
        return False
    content = last_user_msgs[-1]["content"].lower().strip()
    return any(kw in content for kw in _SKIP_KEYWORDS)


async def route_deliberation(state: DeliberationState) -> str:
    """Conditional edge: decide which phase-node to invoke next.

    Uses a hybrid approach: deterministic rules first for speed and
    reliability, with an LLM fallback for ambiguous cases.
    """
    current_phase = state.get("phase", DeliberationPhase.PROBING.value)
    phase_turns = state.get("phase_turn_count", 0)
    total_turns = state.get("turn_count", 0)
    max_turns = 12  # keep conversations short
    should_complete = state.get("should_complete", False)

    # Already done
    if current_phase == DeliberationPhase.COMPLETE.value or should_complete:
        return "summarize"

    # Hard cap on total turns
    if total_turns >= max_turns:
        return "summarize"

    # User explicitly wants to skip
    if _user_wants_to_skip(state.get("messages", [])):
        next_p = _next_phase(current_phase)
        if next_p == DeliberationPhase.COMPLETE.value:
            return "summarize"
        return _phase_to_node(next_p)

    # Phase budget exhausted — advance
    budget = _PHASE_MAX_TURNS.get(current_phase, 3)
    if phase_turns >= budget:
        next_p = _next_phase(current_phase)
        if next_p == DeliberationPhase.COMPLETE.value:
            return "summarize"
        # Reset phase turn count — engine handles this in process_message
        return _phase_to_node(next_p)

    # Otherwise stay in the current phase
    return _phase_to_node(current_phase)


async def route_deliberation_with_llm(state: DeliberationState) -> str:
    """LLM-backed routing for cases where deterministic rules are ambiguous.

    This is available as an alternative to the rule-based router but is
    slower due to the extra LLM call.  The engine can swap routers.
    """
    llm = _get_llm()
    current_phase = state.get("phase", DeliberationPhase.PROBING.value)
    phase_turns = state.get("phase_turn_count", 0)
    total_turns = state.get("turn_count", 0)
    max_turns = 20

    prompt = ROUTE_PROMPT.format(
        current_phase=current_phase,
        turn_count=total_turns,
        phase_turn_count=phase_turns,
        max_turns=max_turns,
        conversation_history=_format_conversation(state.get("messages", [])),
    )

    try:
        result = await llm.structured_output(
            messages=[{"role": "user", "content": "Route the deliberation."}],
            system_prompt=prompt,
            temperature=0.1,
        )
        next_phase = result.get("next_phase", "").strip().lower()

        # Validate
        valid_phases = {p.value for p in DeliberationPhase}
        if next_phase not in valid_phases:
            logger.warning("LLM returned invalid phase '%s', falling back", next_phase)
            return await route_deliberation(state)

        if next_phase == DeliberationPhase.COMPLETE.value:
            return "summarize"
        return _phase_to_node(next_phase)
    except Exception as exc:
        logger.warning("LLM routing failed (%s), using rule-based fallback", exc)
        return await route_deliberation(state)


def _phase_to_node(phase: str) -> str:
    """Map a DeliberationPhase value to its LangGraph node name."""
    mapping = {
        DeliberationPhase.PROBING.value: "probe",
        DeliberationPhase.REQUIREMENTS.value: "requirements",
        DeliberationPhase.COGNITIVE_FORCING.value: "cognitive_forcing",
        DeliberationPhase.CHALLENGE.value: "challenge",
        DeliberationPhase.PREMORTEM.value: "premortem",
        DeliberationPhase.SUMMARY.value: "summarize",
        DeliberationPhase.COMPLETE.value: "summarize",
    }
    return mapping.get(phase, "probe")
