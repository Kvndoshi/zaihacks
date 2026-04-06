"""Build and compile the LangGraph deliberation state-graph.

The graph implements a turn-based conversation loop:

    user sends message
        -> process_input (pass-through)
        -> route_deliberation (conditional edge picks phase)
        -> <phase node> (LLM generates response)
        -> END  (pause — wait for next user message)

The engine re-invokes the compiled graph on every new user turn.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from backend.deliberation.nodes import (
    challenge_node,
    cognitive_forcing_node,
    premortem_node,
    probe_node,
    process_user_input_node,
    requirements_node,
    route_deliberation,
    summarize_node,
)
from backend.deliberation.state import DeliberationState


def build_deliberation_graph():
    """Construct and compile the deliberation StateGraph."""

    graph = StateGraph(DeliberationState)

    # -- Register nodes ------------------------------------------------
    graph.add_node("process_input", process_user_input_node)
    graph.add_node("probe", probe_node)
    graph.add_node("requirements", requirements_node)
    graph.add_node("cognitive_forcing", cognitive_forcing_node)
    graph.add_node("challenge", challenge_node)
    graph.add_node("premortem", premortem_node)
    graph.add_node("summarize", summarize_node)

    # -- Entry point ---------------------------------------------------
    graph.set_entry_point("process_input")

    # -- Conditional routing after processing user input ----------------
    graph.add_conditional_edges(
        "process_input",
        route_deliberation,
        {
            "probe": "probe",
            "requirements": "requirements",
            "cognitive_forcing": "cognitive_forcing",
            "challenge": "challenge",
            "premortem": "premortem",
            "summarize": "summarize",
        },
    )

    # -- Every phase node terminates the current invocation ------------
    # The engine will re-invoke the graph when the next user message
    # arrives, so each phase node simply edges to END.
    for node_name in ("probe", "requirements", "cognitive_forcing", "challenge", "premortem", "summarize"):
        graph.add_edge(node_name, END)

    return graph.compile()
