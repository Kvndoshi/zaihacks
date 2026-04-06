"""Board status endpoint — ticket stats for a session."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/sessions/{session_id}/status")
async def get_board_status(session_id: str, request: Request):
    """Return aggregate ticket stats for the session."""
    manager = request.app.state.manager
    board = await manager.get_board_state(session_id)
    stats = board.get("stats", {})

    # Add layer breakdown
    tickets = board.get("tickets", [])
    layers: dict[int, dict] = {}
    for t in tickets:
        layer = t["layer"] if isinstance(t, dict) else t.layer
        if layer not in layers:
            layers[layer] = {"total": 0, "completed": 0}
        layers[layer]["total"] += 1
        status = t["status"] if isinstance(t, dict) else t.status.value
        if status == "completed":
            layers[layer]["completed"] += 1

    return {
        **stats,
        "layers": layers,
    }
