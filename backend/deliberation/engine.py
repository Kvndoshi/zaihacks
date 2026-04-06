"""High-level deliberation engine — orchestrates sessions and graph runs.

Usage::

    from backend.services.llm import LLMClient
    from backend.deliberation.engine import DeliberationEngine

    llm = LLMClient()
    engine = DeliberationEngine(llm)

    session = await engine.start_session("Build a CLI for X")
    # session.messages[-1] is Friction's first probing response

    msg = await engine.process_message(session.id, "Here's my answer…")
    # msg is Friction's next reply
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.deliberation.graph import build_deliberation_graph
from backend.deliberation.nodes import set_llm_client
from backend.deliberation.state import DeliberationPhase, DeliberationState
from backend.models.session import (
    DeliberationSession,
    MessageRole,
    SessionMessage,
    SessionStatus,
)
from backend.services import db as db_service
from backend.services.llm import LLMClient

logger = logging.getLogger(__name__)


class DeliberationEngine:
    """Manages deliberation sessions and drives the LangGraph graph."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client
        self.graph = build_deliberation_graph()
        # In-memory state cache keyed by session_id.
        # For a hackathon this is fine; in production you'd persist state.
        self._states: dict[str, DeliberationState] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_session(
        self,
        idea: str,
        codebase_summary: str = "",
    ) -> DeliberationSession:
        """Create a new deliberation session and generate Friction's opening probe."""

        session_id = str(uuid.uuid4())

        # Persist session model
        session = DeliberationSession(
            id=session_id,
            title=idea[:80] + ("…" if len(idea) > 80 else ""),
            idea=idea,
            status=SessionStatus.DELIBERATING,
        )
        await db_service.save_session(session)

        # Initialise graph state
        initial_state: DeliberationState = {
            "session_id": session_id,
            "idea": idea,
            "messages": [],  # no user message yet — first run will use the idea
            "phase": DeliberationPhase.PROBING.value,
            "turn_count": 0,
            "phase_turn_count": 0,
            "user_confidence_scores": {},
            "ai_confidence_scores": {},
            "key_insights": [],
            "risks": [],
            "refined_idea": "",
            "codebase_summary": codebase_summary,
            "should_complete": False,
            "web_searched": False,
        }

        # Inject LLM client for nodes to use
        set_llm_client(self.llm)

        # Run graph — process_input is a no-op, router sends to probe_node
        result_state = await self.graph.ainvoke(initial_state)
        self._states[session_id] = result_state

        # Persist the first Friction message
        friction_content = self._latest_friction_message(result_state)
        friction_msg = SessionMessage(
            role=MessageRole.FRICTION,
            content=friction_content,
            phase=result_state.get("phase", DeliberationPhase.PROBING.value),
            web_searched=result_state.get("web_searched", False),
        )
        session.messages.append(friction_msg)
        session.updated_at = datetime.now(timezone.utc)
        await db_service.update_session(session)

        return session

    async def process_message(
        self,
        session_id: str,
        content: str,
        confidence_scores: dict[str, float] | None = None,
    ) -> SessionMessage:
        """Accept a user message, run the graph, and return Friction's reply."""

        state = self._states.get(session_id)

        # Retrieve session from DB for persistence
        session = await db_service.get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found in database")

        # Restore engine state from DB if missing (e.g. after server restart)
        if state is None:
            state = self._restore_state(session)
            self._states[session_id] = state

        # Append user message to graph state
        state["messages"] = list(state["messages"]) + [
            {"role": "user", "content": content}
        ]

        # Record confidence scores if provided
        if confidence_scores:
            merged = dict(state.get("user_confidence_scores", {}))
            merged.update(confidence_scores)
            state["user_confidence_scores"] = merged

        # Detect phase transitions: if the router will advance the phase,
        # reset phase_turn_count so the new phase starts fresh.
        old_phase = state.get("phase", DeliberationPhase.PROBING.value)

        # Persist user message to session
        user_msg = SessionMessage(
            role=MessageRole.USER,
            content=content,
            phase=old_phase,
            confidence_score=(
                sum(confidence_scores.values()) / len(confidence_scores)
                if confidence_scores
                else None
            ),
        )
        session.messages.append(user_msg)

        # Inject LLM and run graph
        set_llm_client(self.llm)
        result_state = await self.graph.ainvoke(state)

        # Detect if phase changed and reset phase_turn_count accordingly
        new_phase = result_state.get("phase", old_phase)
        if new_phase != old_phase:
            result_state["phase_turn_count"] = 1  # just completed the first turn of new phase

        self._states[session_id] = result_state

        # Build response message
        friction_content = self._latest_friction_message(result_state)
        friction_msg = SessionMessage(
            role=MessageRole.FRICTION,
            content=friction_content,
            phase=new_phase,
            web_searched=result_state.get("web_searched", False),
        )
        session.messages.append(friction_msg)

        # Sync summary fields if deliberation completed
        if result_state.get("should_complete"):
            session.status = SessionStatus.COMPLETED
            session.key_insights = result_state.get("key_insights", [])
            session.risks = result_state.get("risks", [])
            session.refined_idea = result_state.get("refined_idea")

        session.updated_at = datetime.now(timezone.utc)
        await db_service.update_session(session)

        return friction_msg

    async def force_complete(self, session_id: str) -> DeliberationSession:
        """Force the deliberation into the summary phase and complete it."""

        state = self._states.get(session_id)
        if state is None:
            session = await db_service.get_session(session_id)
            if session is None:
                raise ValueError(f"Session {session_id} not found in database")
            state = self._restore_state(session)
            self._states[session_id] = state

        # Override state to jump to summary
        state["phase"] = DeliberationPhase.SUMMARY.value
        state["phase_turn_count"] = 0
        state["should_complete"] = True

        set_llm_client(self.llm)
        result_state = await self.graph.ainvoke(state)
        self._states[session_id] = result_state

        # Update session
        session = await db_service.get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found in database")

        friction_content = self._latest_friction_message(result_state)
        friction_msg = SessionMessage(
            role=MessageRole.FRICTION,
            content=friction_content,
            phase=DeliberationPhase.COMPLETE.value,
            web_searched=result_state.get("web_searched", False),
        )
        session.messages.append(friction_msg)
        session.status = SessionStatus.COMPLETED
        session.key_insights = result_state.get("key_insights", [])
        session.risks = result_state.get("risks", [])
        session.refined_idea = result_state.get("refined_idea")
        session.updated_at = datetime.now(timezone.utc)
        await db_service.update_session(session)

        return session

    async def get_session(self, session_id: str) -> DeliberationSession | None:
        """Retrieve a session from the database."""
        return await db_service.get_session(session_id)

    def get_current_phase(self, session_id: str) -> str | None:
        """Return the current deliberation phase for a session."""
        state = self._states.get(session_id)
        if state is None:
            return None
        return state.get("phase")

    def get_state(self, session_id: str) -> DeliberationState | None:
        """Return the raw graph state (useful for debugging / the frontend)."""
        return self._states.get(session_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _restore_state(session: DeliberationSession) -> DeliberationState:
        """Reconstruct a DeliberationState from a DB-loaded session.

        This allows resuming deliberation after a server restart.
        """
        # Rebuild messages list from session messages
        messages: list[dict[str, str]] = []
        last_phase = DeliberationPhase.PROBING.value
        for msg in session.messages:
            role = msg.role.value if hasattr(msg.role, "value") else msg.role
            messages.append({"role": role, "content": msg.content})
            if msg.phase:
                last_phase = msg.phase

        # Guess current phase from the last message's phase
        phase = last_phase
        if session.status == SessionStatus.COMPLETED:
            phase = DeliberationPhase.COMPLETE.value

        logger.info("Restored engine state for session %s (phase=%s, %d messages)",
                     session.id, phase, len(messages))

        return {
            "session_id": session.id,
            "idea": session.idea,
            "messages": messages,
            "phase": phase,
            "turn_count": len([m for m in messages if m["role"] == "friction"]),
            "phase_turn_count": 0,
            "user_confidence_scores": {},
            "ai_confidence_scores": {},
            "key_insights": session.key_insights or [],
            "risks": session.risks or [],
            "refined_idea": session.refined_idea or "",
            "codebase_summary": "",  # Will be set by inject-codebase if needed
            "should_complete": session.status == SessionStatus.COMPLETED,
            "web_searched": False,
        }

    @staticmethod
    def _latest_friction_message(state: DeliberationState) -> str:
        """Extract the most recent Friction message from state."""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "friction":
                return msg["content"]
        return "(Friction had nothing to say — this shouldn't happen.)"
