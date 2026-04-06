"""Session endpoints — create, list, message, and complete deliberation sessions."""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.models.events import EventType, WSEvent
from backend.models.session import DeliberationSession, MessageRole, SessionMessage
from backend.services.db import save_session, get_session, list_sessions, update_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    idea: str
    codebase_id: Optional[str] = None


class SendMessageRequest(BaseModel):
    content: str
    confidence_scores: Optional[dict] = None


class RefineRequest(BaseModel):
    content: str


class InjectCodebaseRequest(BaseModel):
    analysis_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=DeliberationSession)
async def create_session(body: CreateSessionRequest, request: Request):
    """Create a new deliberation session and return the first Friction probe."""
    engine = request.app.state.engine
    ws_manager = request.app.state.ws_manager

    session = await engine.start_session(
        idea=body.idea,
    )
    await save_session(session)

    # Broadcast session creation
    await ws_manager.broadcast(
        WSEvent(
            type=EventType.SESSION_CREATED,
            session_id=session.id,
            data={"title": session.title, "idea": session.idea},
        )
    )

    return session


@router.get("/", response_model=list[DeliberationSession])
async def get_all_sessions():
    """List every deliberation session."""
    return await list_sessions()


@router.get("/{session_id}", response_model=DeliberationSession)
async def get_session_detail(session_id: str):
    """Return a single session with all its messages."""
    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/{session_id}/agent-prompt")
async def get_agent_prompt(session_id: str):
    """Return the agent prompt — session-specific if available, universal otherwise."""
    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.agent_prompt:
        return {"prompt": session.agent_prompt, "session_id": session_id}

    # No session-specific prompt yet — return universal prompt with session ID appended
    from backend.tickets.prompt_generator import get_universal_prompt
    prompt = get_universal_prompt()
    prompt += f"\n\n---\n\n## Start Here\n\n```\nuse_session(\"{session_id}\")\n```\n\nThen call `get_next_ticket` to begin."
    return {"prompt": prompt, "session_id": session_id}


@router.post("/{session_id}/message", response_model=SessionMessage)
async def send_message(session_id: str, body: SendMessageRequest, request: Request):
    """Send a user message into the deliberation and receive the AI response."""
    engine = request.app.state.engine
    ws_manager = request.app.state.ws_manager

    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    ai_message = await engine.process_message(
        session_id=session_id,
        content=body.content,
        confidence_scores=body.confidence_scores,
    )

    # Persist the updated session (engine mutates in-memory; re-fetch)
    updated_session = await engine.get_session(session_id)
    if updated_session is not None:
        await save_session(updated_session)

    # Broadcast the new message
    await ws_manager.broadcast(
        WSEvent(
            type=EventType.SESSION_MESSAGE,
            session_id=session_id,
            data={
                "message_id": ai_message.id,
                "role": ai_message.role.value,
                "content": ai_message.content,
                "phase": ai_message.phase,
                "web_searched": ai_message.web_searched,
            },
        )
    )

    return ai_message


@router.post("/{session_id}/complete", response_model=DeliberationSession)
async def complete_session(session_id: str, request: Request):
    """End deliberation, generate tickets, and create them on the board."""
    engine = request.app.state.engine
    generator = request.app.state.generator
    manager = request.app.state.manager
    ws_manager = request.app.state.ws_manager

    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        # 1. Force-complete the deliberation
        session = await engine.force_complete(session_id)

        # 2. Optionally fetch codebase analysis if linked
        codebase = None
        if session.codebase_id:
            from backend.services.db import get_codebase_analysis

            codebase = await get_codebase_analysis(session.codebase_id)

        # 3. Generate ticket specs from the refined session
        tickets = await generator.generate(session, codebase)

        # 4. Persist tickets & wire up dependency graph via TicketManager
        created = await manager.create_tickets(session.id, tickets)

        # 5. Generate agent prompt
        from backend.tickets.prompt_generator import generate_agent_prompt
        session.agent_prompt = generate_agent_prompt(session, created, codebase)

        # 6. Persist session
        await save_session(session)

        # 7. Broadcast events
        await ws_manager.broadcast(
            WSEvent(
                type=EventType.DELIBERATION_COMPLETE,
                session_id=session_id,
                data={
                    "refined_idea": session.refined_idea,
                    "key_insights": session.key_insights,
                    "risks": session.risks,
                },
            )
        )
        await ws_manager.broadcast(
            WSEvent(
                type=EventType.TICKETS_GENERATED,
                session_id=session_id,
                data={
                    "ticket_count": len(created),
                    "ticket_ids": [t.id for t in created],
                },
            )
        )

        return session
    except Exception as e:
        logger.exception("Failed to complete session %s", session_id)
        raise HTTPException(status_code=500, detail=f"Completion failed: {e}")


@router.post("/{session_id}/refine", response_model=SessionMessage)
async def refine_tickets(session_id: str, body: RefineRequest, request: Request):
    """Post-completion chat: refine tickets based on user instructions."""
    manager = request.app.state.manager
    ws_manager = request.app.state.ws_manager
    llm = request.app.state.llm

    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status.value != "completed":
        raise HTTPException(status_code=400, detail="Session must be completed to refine tickets")

    # Fetch current tickets
    board = await manager.get_board_state(session_id)
    tickets = board["tickets"]

    # Build ticket summary for LLM
    ticket_summary = json.dumps(
        [
            {
                "id": t["id"],
                "title": t["title"],
                "description": t["description"][:200],
                "layer": t["layer"],
                "domain": t["domain"],
                "status": t["status"],
                "depends_on": t["depends_on"],
            }
            for t in tickets
        ],
        indent=2,
    )

    system_prompt = (
        "You are a project planning assistant. The user has already generated tickets "
        "from a deliberation and now wants to refine them.\n\n"
        f"Original idea: {session.idea}\n\n"
        f"Current tickets:\n{ticket_summary}\n\n"
        "Based on the user's message, return a JSON object:\n"
        '{"actions": [...], "response": "human-readable summary of changes"}\n\n'
        "Each action is one of:\n"
        '- {"action": "add", "title": "...", "description": "...", "layer": 0, "domain": "backend", "priority": "medium", "depends_on": [], "acceptance_criteria": [...]}\n'
        '- {"action": "modify", "ticket_id": "FRIC-XXX", ...changed fields only (title, description, acceptance_criteria, domain, priority)}\n'
        '- {"action": "delete", "ticket_id": "FRIC-XXX"}\n\n'
        "If the user is just chatting/asking questions, return empty actions and a helpful response."
    )

    try:
        result = await llm.structured_output(
            messages=[{"role": "user", "content": body.content}],
            system_prompt=system_prompt,
            temperature=0.4,
        )

        actions = result.get("actions", [])
        response_text = result.get("response", "Done.")

        # Execute actions
        from backend.services.db import save_ticket as db_save_ticket
        from backend.models.ticket import Ticket, TicketStatus

        for action in actions:
            act = action.get("action")
            if act == "delete":
                tid = action.get("ticket_id")
                if tid:
                    await manager.delete_ticket(session_id, tid)
            elif act == "modify":
                tid = action.get("ticket_id")
                if tid:
                    from backend.services.db import get_ticket as db_get_ticket
                    ticket = await db_get_ticket(tid)
                    if ticket:
                        for field in ("title", "description", "acceptance_criteria", "domain", "priority"):
                            if field in action:
                                setattr(ticket, field, action[field])
                        await db_save_ticket(ticket)
                        # Update cache
                        await manager._load_session_tickets(session_id)
                        store = manager._tickets.get(session_id, {})
                        store[ticket.id] = ticket
            elif act == "add":
                # Find the next available FRIC-XXX id
                existing_ids = [t["id"] for t in tickets]
                max_num = 0
                for eid in existing_ids:
                    try:
                        num = int(eid.split("-")[1])
                        max_num = max(max_num, num)
                    except (IndexError, ValueError):
                        pass
                new_id = f"FRIC-{max_num + 1:03d}"
                max_num += 1

                new_ticket = Ticket(
                    id=new_id,
                    session_id=session_id,
                    title=action.get("title", "New Ticket"),
                    description=action.get("description", ""),
                    layer=action.get("layer", 0),
                    domain=action.get("domain", "backend"),
                    priority=action.get("priority", 2),
                    status=TicketStatus.READY if not action.get("depends_on") else TicketStatus.BLOCKED,
                    depends_on=action.get("depends_on", []),
                    acceptance_criteria=action.get("acceptance_criteria", []),
                    files_to_create=action.get("files_to_create", []),
                    files_to_modify=action.get("files_to_modify", []),
                )
                await manager.create_tickets(session_id, [new_ticket])

        # Persist messages
        user_msg = SessionMessage(role=MessageRole.USER, content=body.content)
        ai_msg = SessionMessage(role=MessageRole.FRICTION, content=response_text)
        session.messages.append(user_msg)
        session.messages.append(ai_msg)
        await save_session(session)

        # Broadcast
        await ws_manager.broadcast(
            WSEvent(
                type=EventType.TICKETS_REFINED,
                session_id=session_id,
                data={"actions_count": len(actions)},
            )
        )

        return ai_msg
    except Exception as e:
        logger.error("Failed to refine tickets: %s", e)
        raise HTTPException(status_code=500, detail=f"Refinement failed: {e}")


@router.post("/{session_id}/inject-codebase", response_model=SessionMessage)
async def inject_codebase(session_id: str, body: InjectCodebaseRequest, request: Request):
    """Inject a codebase analysis into the deliberation — adds a friction
    message with the analysis summary and updates the engine's internal state
    so all subsequent LLM calls are codebase-aware."""
    engine = request.app.state.engine
    ws_manager = request.app.state.ws_manager

    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    from backend.services.db import get_codebase_analysis
    analysis = await get_codebase_analysis(body.analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Build a rich codebase summary for the engine
    parts = [analysis.summary]
    ts = analysis.tech_stack
    if ts.languages:
        lang_str = ", ".join(f"{lang} ({cnt} files)" for lang, cnt in ts.languages.items())
        parts.append(f"Languages: {lang_str}")
    if ts.frameworks:
        parts.append(f"Frameworks: {', '.join(ts.frameworks)}")
    if ts.databases:
        parts.append(f"Databases: {', '.join(ts.databases)}")
    if analysis.key_files:
        key_paths = [f.path for f in analysis.key_files[:15]]
        parts.append("Key files: " + ", ".join(key_paths))
    if analysis.architecture_patterns:
        patterns = [f"{p.name} ({p.confidence:.0%})" for p in analysis.architecture_patterns]
        parts.append(f"Architecture: {', '.join(patterns)}")
    codebase_summary = "\n".join(parts)

    # Update the engine's in-memory state so subsequent LLM calls include the codebase
    engine_state = engine._states.get(session_id)
    if engine_state is None:
        # Restore engine state from DB so the user can continue chatting
        engine_state = engine._restore_state(session)
        engine._states[session_id] = engine_state
    engine_state["codebase_summary"] = codebase_summary

    # Link codebase to session
    session.codebase_id = body.analysis_id

    # Build a user-facing friction message
    repo_name = analysis.repo_url or "the repository"
    frameworks_str = ", ".join(ts.frameworks) if ts.frameworks else "no major frameworks detected"
    languages_str = ", ".join(ts.languages.keys()) if ts.languages else "unknown"

    display_text = (
        f"I've analyzed {repo_name}. Here's what I found:\n\n"
        f"{analysis.summary}\n\n"
        f"Tech stack: {languages_str}. Frameworks: {frameworks_str}. "
        f"{analysis.file_count} files, {analysis.total_size / 1024:.0f} KB total.\n\n"
        f"Now — what do you want to do with this codebase? "
        f"Add a feature? Fix something? Refactor? Tell me your plan and I'll challenge it."
    )

    friction_msg = SessionMessage(
        role=MessageRole.FRICTION,
        content=display_text,
        phase="probing",
    )
    session.messages.append(friction_msg)
    await update_session(session)

    # Also inject into engine state messages so LLM has context
    engine_state["messages"] = list(engine_state.get("messages", [])) + [
        {"role": "friction", "content": display_text}
    ]

    await ws_manager.broadcast(
        WSEvent(
            type=EventType.SESSION_MESSAGE,
            session_id=session_id,
            data={
                "message_id": friction_msg.id,
                "role": "friction",
                "content": display_text,
            },
        )
    )

    return friction_msg
