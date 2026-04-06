"""Generate agent prompts for the Friction system.

Two types:
1. Universal prompt — teaches any LLM how to use Friction MCP tools.
   This is the default prompt shown to users. Session-agnostic.
2. Session-specific prompt — includes project context from deliberation.
   Used when a session is completed and we want to give extra context.
"""

from __future__ import annotations

from backend.models.codebase import CodebaseAnalysis
from backend.models.session import DeliberationSession
from backend.models.ticket import Ticket


# ---------------------------------------------------------------------------
# Universal prompt — the main one users copy-paste into Claude/Cursor
# ---------------------------------------------------------------------------

UNIVERSAL_AGENT_PROMPT = """\
# Friction Agent — Autonomous Ticket Worker

You are connected to a **Friction MCP server** — a ticket orchestration system that breaks projects into dependency-ordered tasks. Your job is to pick up tickets, implement them, and report back.

## Workflow

Follow this loop until all tickets are done:

1. **Discover** — Call `list_sessions` to see available projects.
2. **Select** — Call `use_session` with the session ID you want to work on. All subsequent tools will use this session automatically.
3. **Claim** — Call `get_next_ticket` to atomically claim the next available ticket. No one else will get the same ticket. The system handles dependency ordering — you only see tickets whose prerequisites are complete.
4. **Read** — The ticket includes:
   - Description of what to build/do
   - Acceptance criteria (your checklist)
   - Files to create and modify (if applicable)
   - Dependency outputs — summaries from completed upstream tickets (read these carefully, they contain context and decisions you need)
5. **Implement** — Do the work described in the ticket.
6. **Complete** — Call `mark_done` with a detailed `output_summary`:
   - What you built / what was done
   - Files created or modified
   - Key decisions you made and why
   - Any known issues, bugs, or workarounds
   - How to verify / test your work
   This summary is **critical** — downstream tickets receive it as context.
7. **Repeat** — Go back to step 3. Keep going until `get_next_ticket` returns "no tickets available."

If you hit a blocker you can't resolve, call `fail_ticket` with a clear error description instead.

## MCP Tools Reference

| Tool | Purpose |
|------|---------|
| `list_sessions` | See all projects — shows ID, title, status |
| `use_session` | Set active project (call once at start) |
| `get_next_ticket` | Claim next ready ticket (atomic, no conflicts) |
| `mark_done` | Complete a ticket — requires output_summary |
| `fail_ticket` | Mark ticket as failed — requires error reason |
| `list_tickets` | View all tickets grouped by status |
| `get_ticket_context` | Read a specific ticket + dependency outputs |
| `get_status` | Board stats — counts, progress % |
| `get_workflow` | Dependency graph (which tickets block which) |

## Rules

- **One ticket at a time.** Claim, implement, complete — then claim the next.
- **Respect dependency order.** The system only gives you tickets whose dependencies are done. Don't try to skip ahead.
- **Write real code.** No placeholders, no TODOs, no "implement this later." Each ticket should be shippable.
- **output_summary matters.** Downstream tickets depend on your summary to understand what was built. Be specific.
- **Non-technical tickets exist.** Some tickets may be for design, marketing, research, operations, etc. — not just code. Handle them appropriately.
- **Check status when unsure.** Call `get_status` to see overall progress or `list_tickets` to see what's blocked/ready.
"""


def get_universal_prompt() -> str:
    """Return the universal agent prompt (no session context needed)."""
    return UNIVERSAL_AGENT_PROMPT.strip()


# ---------------------------------------------------------------------------
# Session-specific prompt — adds project context on top of universal prompt
# ---------------------------------------------------------------------------

def generate_agent_prompt(
    session: DeliberationSession,
    tickets: list[Ticket],
    codebase: CodebaseAnalysis | None = None,
) -> str:
    """Build an agent prompt with session-specific context appended."""

    sections: list[str] = [get_universal_prompt()]

    # --- Project Context ---
    sections.append("")
    sections.append("---")
    sections.append("")
    sections.append(f"## Project Context: {session.title}")
    sections.append("")

    if session.refined_idea:
        sections.append(f"**What we're building:** {session.refined_idea}")
    else:
        sections.append(f"**Idea:** {session.idea}")

    # Key insights (compact)
    if session.key_insights:
        sections.append("")
        sections.append("**Key insights from deliberation:**")
        for insight in session.key_insights:
            sections.append(f"- {insight}")

    # Risks (compact)
    if session.risks:
        sections.append("")
        sections.append("**Risks to watch:**")
        for risk in session.risks:
            sections.append(f"- {risk}")

    # Codebase (compact)
    if codebase:
        sections.append("")
        parts = []
        if codebase.repo_url:
            parts.append(f"Repo: {codebase.repo_url}")
        parts.append(f"{codebase.file_count} files, {codebase.total_size / 1024:.0f} KB")
        ts = codebase.tech_stack
        if ts.languages:
            parts.append(f"Languages: {', '.join(ts.languages.keys())}")
        if ts.frameworks:
            parts.append(f"Frameworks: {', '.join(ts.frameworks)}")
        sections.append(f"**Codebase:** {' | '.join(parts)}")

    # Ticket count
    sections.append("")
    sections.append(f"**Tickets:** {len(tickets)} across {_count_layers(tickets)} layers")

    # Session ID — the key piece
    sections.append("")
    sections.append("## Start Here")
    sections.append("")
    sections.append(f"```")
    sections.append(f"use_session(\"{session.id}\")")
    sections.append(f"```")
    sections.append("")
    sections.append("Then call `get_next_ticket` to begin.")

    return "\n".join(sections)


def _count_layers(tickets: list[Ticket]) -> int:
    if not tickets:
        return 0
    return len(set(t.layer for t in tickets))
