"""Workflow graph endpoint — serves ReactFlow-compatible dependency DAG."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request

from backend.models.workflow import WorkflowEdge, WorkflowGraph, WorkflowNode
from backend.services.db import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["workflow"])


@router.get("/sessions/{session_id}/workflow", response_model=WorkflowGraph)
async def get_workflow(session_id: str, request: Request):
    """Return the dependency graph for a session's tickets."""
    manager = request.app.state.manager
    try:
        graph = await manager.get_workflow(session_id)
        return graph
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# Component type to color mapping for architecture nodes
_COMPONENT_COLORS = {
    "frontend": "#8b5cf6",
    "backend": "#3b82f6",
    "database": "#10b981",
    "api": "#06b6d4",
    "auth": "#ef4444",
    "infra": "#f97316",
    "testing": "#eab308",
    "docs": "#6b7280",
}


@router.get("/sessions/{session_id}/architecture", response_model=WorkflowGraph)
async def get_architecture(session_id: str, request: Request):
    """Generate a high-level system architecture diagram from tickets."""
    manager = request.app.state.manager
    llm = request.app.state.llm

    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    board = await manager.get_board_state(session_id)
    tickets = board["tickets"]

    if not tickets:
        raise HTTPException(status_code=404, detail="No tickets to generate architecture from")

    ticket_summary = json.dumps(
        [{"id": t["id"], "title": t["title"], "domain": t["domain"], "layer": t["layer"]}
         for t in tickets],
        indent=2,
    )

    system_prompt = (
        "You are a software architect. Given these implementation tickets, generate a "
        "high-level system architecture with major components and their connections.\n\n"
        f"Project idea: {session.idea}\n\n"
        f"Tickets:\n{ticket_summary}\n\n"
        "Return a JSON object:\n"
        '{"components": [{"id": "comp-1", "label": "...", "type": "frontend|backend|database|api|auth|infra", '
        '"description": "short desc", "ticket_ids": ["FRIC-001"]}], '
        '"connections": [{"from": "comp-1", "to": "comp-2", "label": "REST API"}]}\n\n'
        "Generate 3-8 components. Group related tickets into the same component."
    )

    try:
        result = await llm.structured_output(
            messages=[{"role": "user", "content": "Generate the system architecture."}],
            system_prompt=system_prompt,
            temperature=0.3,
        )

        components = result.get("components", [])
        connections = result.get("connections", [])

        # Convert to WorkflowGraph format
        nodes = []
        cols = 3
        for i, comp in enumerate(components):
            row = i // cols
            col = i % cols
            comp_type = comp.get("type", "backend")
            ticket_count = len(comp.get("ticket_ids", []))
            nodes.append(WorkflowNode(
                ticket_id=comp.get("id", f"comp-{i}"),
                label=f"{comp.get('label', 'Component')} ({ticket_count} tickets)",
                layer=row,
                domain=comp_type if comp_type in _COMPONENT_COLORS else "backend",
                status="ready",
                position_x=col * 320 + 50,
                position_y=row * 160 + 50,
            ))

        # Build node id lookup
        comp_id_to_node_id = {comp.get("id", f"comp-{i}"): nodes[i].id for i, comp in enumerate(components)}

        edges = []
        for conn in connections:
            src = comp_id_to_node_id.get(conn.get("from", ""))
            tgt = comp_id_to_node_id.get(conn.get("to", ""))
            if src and tgt:
                edges.append(WorkflowEdge(
                    source=src,
                    target=tgt,
                    animated=True,
                ))

        return WorkflowGraph(nodes=nodes, edges=edges)
    except Exception as e:
        logger.error("Failed to generate architecture: %s", e)
        raise HTTPException(status_code=500, detail=f"Architecture generation failed: {e}")
