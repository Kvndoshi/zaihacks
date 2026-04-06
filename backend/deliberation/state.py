"""Deliberation state schema used by the LangGraph graph."""

from __future__ import annotations

from enum import Enum
from typing import TypedDict


class DeliberationPhase(str, Enum):
    """Phases the deliberation engine moves through sequentially."""

    PROBING = "probing"
    REQUIREMENTS = "requirements"
    COGNITIVE_FORCING = "cognitive_forcing"
    CHALLENGE = "challenge"
    PREMORTEM = "premortem"
    SUMMARY = "summary"
    COMPLETE = "complete"


class DeliberationState(TypedDict):
    """Full state carried through the LangGraph deliberation graph.

    LangGraph merges partial dicts returned by each node, so nodes only
    need to return the keys they want to update.
    """

    session_id: str
    idea: str
    messages: list[dict]  # each entry: {"role": "user"|"friction", "content": str}
    phase: str  # DeliberationPhase value
    turn_count: int
    phase_turn_count: int
    user_confidence_scores: dict  # aspect -> int/float score
    ai_confidence_scores: dict  # aspect -> int/float score
    key_insights: list[str]
    risks: list[str]
    refined_idea: str
    codebase_summary: str
    should_complete: bool
    web_searched: bool  # whether the last response used web search
