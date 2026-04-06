"""Ticket endpoints — CRUD, claiming, and next-ticket orchestration."""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.models.events import EventType, WSEvent
from backend.models.ticket import Ticket, TicketStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["tickets"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class NextTicketRequest(BaseModel):
    agent_id: Optional[str] = None
    agent_role: Optional[str] = None


class UpdateTicketRequest(BaseModel):
    status: Optional[str] = None
    output_summary: Optional[str] = None
    agent_id: Optional[str] = None


class ModifyTicketRequest(BaseModel):
    instruction: str


class IssueGroupActiveRequest(BaseModel):
    active: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/sessions/{session_id}/tickets", response_model=list[Ticket])
async def get_session_tickets(session_id: str, request: Request):
    """Return all tickets for a session."""
    manager = request.app.state.manager
    board = await manager.get_board_state(session_id)
    return board["tickets"]


@router.post("/sessions/{session_id}/tickets/next")
async def get_next_ticket(session_id: str, body: NextTicketRequest, request: Request):
    """Get and atomically claim the next available ticket."""
    manager = request.app.state.manager
    ws_manager = request.app.state.ws_manager

    result = await manager.get_next_ticket(
        session_id=session_id,
        agent_role=body.agent_role,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="No tickets available")

    await ws_manager.broadcast(
        WSEvent(
            type=EventType.TICKET_CLAIMED,
            session_id=session_id,
            data={
                "ticket_id": result["ticket"].id,
                "agent_id": body.agent_id,
                "agent_role": body.agent_role,
            },
        )
    )

    return {
        "ticket": result["ticket"].model_dump(mode="json"),
        "dependency_outputs": result["dependency_outputs"],
    }


@router.delete("/tickets/{ticket_id}")
async def delete_ticket(ticket_id: str, request: Request):
    """Delete a ticket and clean up dependencies."""
    manager = request.app.state.manager
    ws_manager = request.app.state.ws_manager

    from backend.services.db import get_ticket as db_get_ticket

    ticket = await db_get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    deleted = await manager.delete_ticket(ticket.session_id, ticket_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await ws_manager.broadcast(
        WSEvent(
            type=EventType.TICKET_DELETED,
            session_id=ticket.session_id,
            data={"ticket_id": ticket_id},
        )
    )
    await ws_manager.broadcast(
        WSEvent(
            type=EventType.WORKFLOW_UPDATE,
            session_id=ticket.session_id,
            data={"trigger": "ticket_deleted", "ticket_id": ticket_id},
        )
    )

    return {"deleted": True}


@router.post("/tickets/{ticket_id}/modify")
async def modify_ticket(ticket_id: str, body: ModifyTicketRequest, request: Request):
    """Modify a ticket using a natural-language instruction via LLM."""
    manager = request.app.state.manager
    ws_manager = request.app.state.ws_manager
    llm = request.app.state.llm

    from backend.services.db import get_ticket as db_get_ticket, save_ticket as db_save_ticket

    ticket = await db_get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_json = ticket.model_dump(mode="json")
    system_prompt = (
        "You are modifying a project ticket based on a user instruction. "
        "Return the full ticket as a JSON object. "
        "You may change: title, description, acceptance_criteria, domain, priority, "
        "files_to_create, files_to_modify. "
        "Preserve unchanged: id, session_id, layer, depends_on, blocks, status, "
        "output_summary, agent_id, claimed_at, completed_at, created_at.\n\n"
        "Respond with valid JSON only."
    )
    prompt = (
        f"Current ticket:\n```json\n{json.dumps(ticket_json, indent=2)}\n```\n\n"
        f"User instruction: {body.instruction}"
    )

    try:
        result = await llm.structured_output(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=system_prompt,
            temperature=0.3,
        )

        # Update mutable fields
        for field in ("title", "description", "acceptance_criteria", "domain",
                      "priority", "files_to_create", "files_to_modify"):
            if field in result:
                setattr(ticket, field, result[field])

        await db_save_ticket(ticket)

        # Update in-memory cache
        await manager._load_session_tickets(ticket.session_id)
        store = manager._tickets.get(ticket.session_id, {})
        store[ticket.id] = ticket

        await ws_manager.broadcast(
            WSEvent(
                type=EventType.TICKET_MODIFIED,
                session_id=ticket.session_id,
                data={"ticket_id": ticket_id},
            )
        )
        await ws_manager.broadcast(
            WSEvent(
                type=EventType.WORKFLOW_UPDATE,
                session_id=ticket.session_id,
                data={"trigger": "ticket_modified", "ticket_id": ticket_id},
            )
        )

        return ticket.model_dump(mode="json")
    except Exception as e:
        logger.error("Failed to modify ticket %s: %s", ticket_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to modify ticket: {e}")


@router.get("/tickets/{ticket_id}", response_model=Ticket)
async def get_ticket(ticket_id: str, request: Request):
    """Return a single ticket."""
    from backend.services.db import get_ticket as db_get_ticket

    ticket = await db_get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("/tickets/{ticket_id}/context")
async def get_ticket_context(ticket_id: str, request: Request):
    """Return ticket with all completed dependency output summaries."""
    manager = request.app.state.manager

    # We need to find the session_id for this ticket
    from backend.services.db import get_ticket as db_get_ticket

    ticket = await db_get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    context = await manager.get_ticket_context(ticket.session_id, ticket_id)
    return {
        "ticket": context["ticket"].model_dump(mode="json"),
        "dependency_outputs": context["dependency_outputs"],
    }


@router.patch("/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, body: UpdateTicketRequest, request: Request):
    """Update a ticket's status, output, or agent."""
    manager = request.app.state.manager
    ws_manager = request.app.state.ws_manager

    from backend.services.db import get_ticket as db_get_ticket

    ticket = await db_get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if body.status == TicketStatus.COMPLETED.value:
        summary = body.output_summary or "Manually completed"
        updated = await manager.complete_ticket(ticket.session_id, ticket_id, summary)
        await ws_manager.broadcast(
            WSEvent(
                type=EventType.TICKET_COMPLETED,
                session_id=ticket.session_id,
                data={
                    "ticket_id": ticket_id,
                    "output_summary": summary,
                },
            )
        )
        await ws_manager.broadcast(
            WSEvent(
                type=EventType.WORKFLOW_UPDATE,
                session_id=ticket.session_id,
                data={"trigger": "ticket_completed", "ticket_id": ticket_id},
            )
        )
        return updated.model_dump(mode="json")

    if body.status == TicketStatus.FAILED.value:
        updated = await manager.fail_ticket(ticket.session_id, ticket_id, body.output_summary or "Failed")
        await ws_manager.broadcast(
            WSEvent(
                type=EventType.TICKET_FAILED,
                session_id=ticket.session_id,
                data={"ticket_id": ticket_id, "error": body.output_summary},
            )
        )
        return updated.model_dump(mode="json")

    # Generic update (including un-completing: status back to ready)
    from backend.services.db import update_ticket as db_update_ticket

    updates = {}
    if body.status:
        updates["status"] = body.status
    if body.output_summary:
        updates["output_summary"] = body.output_summary
    if body.agent_id:
        updates["agent_id"] = body.agent_id

    updated = await db_update_ticket(ticket_id, **updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Also update in-memory cache
    await manager._load_session_tickets(ticket.session_id)
    store = manager._tickets.get(ticket.session_id, {})
    if updated.id in store:
        store[updated.id] = updated

    await ws_manager.broadcast(
        WSEvent(
            type=EventType.WORKFLOW_UPDATE,
            session_id=ticket.session_id,
            data={"trigger": "ticket_updated", "ticket_id": ticket_id},
        )
    )

    return updated.model_dump(mode="json")


@router.patch("/sessions/{session_id}/issue-group/{source_issue_id}/active")
async def toggle_issue_group(
    session_id: str,
    source_issue_id: str,
    body: IssueGroupActiveRequest,
    request: Request,
):
    """Activate or deactivate all tickets belonging to an issue group."""
    manager = request.app.state.manager
    ws_manager = request.app.state.ws_manager

    updated = await manager.set_issue_group_active(
        session_id, source_issue_id, body.active
    )

    await ws_manager.broadcast(
        WSEvent(
            type=EventType.ISSUE_GROUP_TOGGLED,
            session_id=session_id,
            data={
                "source_issue_id": source_issue_id,
                "active": body.active,
                "ticket_count": len(updated),
            },
        )
    )
    await ws_manager.broadcast(
        WSEvent(
            type=EventType.WORKFLOW_UPDATE,
            session_id=session_id,
            data={"trigger": "issue_group_toggled", "source_issue_id": source_issue_id},
        )
    )

    return [t.model_dump(mode="json") for t in updated]
