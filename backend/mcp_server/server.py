"""Friction MCP Server — exposes deliberation + ticket tools via stdio transport.

Run as: python -m backend.mcp_server
Separate process that calls the Friction FastAPI server over HTTP.

Deliberation tools (idea → debate → tickets):
  - start_deliberation: send idea to server, opens dashboard for deliberation
  - get_agent_prompt: fetch the generated prompt after deliberation is complete

Session management:
  - list_sessions: see all deliberation sessions/projects
  - use_session: set the active session

Ticket tools:
  - get_next_ticket, mark_done, fail_ticket, list_tickets,
    get_ticket_context, get_status, get_workflow
"""

from __future__ import annotations

import json
import logging
import os
import webbrowser

import aiohttp
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

logger = logging.getLogger(__name__)

_BASE_URL = os.getenv("FRICTION_API_BASE", "http://localhost:3001")
FRICTION_API_URL = _BASE_URL + "/api"
FRICTION_DASHBOARD_URL = _BASE_URL

server = Server("friction-mcp")

# ---------------------------------------------------------------------------
# Active session — set via use_session, used as default for all tools
# ---------------------------------------------------------------------------
_active_session_id: str | None = None
_active_session_title: str | None = None


def _resolve_session(arguments: dict) -> str | None:
    """Return the session ID from arguments or the active session."""
    return arguments.get("session_id") or _active_session_id


def _require_session(arguments: dict) -> str:
    """Return session ID or raise a helpful error."""
    sid = _resolve_session(arguments)
    if not sid:
        raise ValueError(
            "No active session. Call `list_sessions` to see available projects, "
            "then `use_session` to pick one."
        )
    return sid


# ---------------------------------------------------------------------------
# Helper — format a ticket dict as readable markdown
# ---------------------------------------------------------------------------

def _format_ticket(ticket: dict, dep_outputs: dict | None = None) -> str:
    """Turn a ticket JSON dict into agent-friendly markdown."""
    lines = [
        f"# Ticket {ticket['id']}: {ticket['title']}",
        f"**Status**: {ticket['status']} | **Domain**: {ticket['domain']} "
        f"| **Priority**: {ticket.get('priority', '?')} | **Layer**: {ticket.get('layer', '?')}",
    ]

    if ticket.get("source_issue_title"):
        lines.append(f"**Source issue**: {ticket['source_issue_title']}")

    if not ticket.get("active", True):
        lines.append("**PAUSED** — this ticket's issue group is deactivated")

    lines.extend(["", "## Description", ticket.get("description", "")])

    if ticket.get("acceptance_criteria"):
        lines.append("\n## Acceptance Criteria")
        for ac in ticket["acceptance_criteria"]:
            lines.append(f"- [ ] {ac}")

    if ticket.get("files_to_create"):
        lines.append("\n## Files to Create")
        for f in ticket["files_to_create"]:
            lines.append(f"- `{f}`")

    if ticket.get("files_to_modify"):
        lines.append("\n## Files to Modify")
        for f in ticket["files_to_modify"]:
            lines.append(f"- `{f}`")

    if dep_outputs:
        lines.append("\n## Dependency Outputs (from completed prerequisite tickets)")
        for dep_id, summary in dep_outputs.items():
            lines.append(f"\n### {dep_id}\n{summary}")

    if ticket.get("depends_on"):
        lines.append(f"\n**Depends on**: {', '.join(ticket['depends_on'])}")
    if ticket.get("blocks"):
        lines.append(f"**Blocks**: {', '.join(ticket['blocks'])}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ----- Deliberation tools -----
        Tool(
            name="start_deliberation",
            description=(
                "Start a new project deliberation. Sends the user's idea to the Friction "
                "server, creates a session, and opens the dashboard in the browser where "
                "the user will debate their idea with the Friction AI. "
                "CALL THIS when the user describes a new project idea or says they want to "
                "build something. After calling this, tell the user to complete the "
                "deliberation in the browser, then come back to Cursor."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "idea": {
                        "type": "string",
                        "description": "The user's project idea or description of what they want to build/do.",
                    },
                },
                "required": ["idea"],
            },
        ),
        Tool(
            name="get_agent_prompt",
            description=(
                "Fetch the agent prompt generated after deliberation is complete. "
                "Call this after the user says they finished deliberating in the dashboard. "
                "Returns the full prompt with project context, tickets, and instructions. "
                "Uses the active session."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Optional — overrides the active session.",
                    },
                },
            },
        ),
        # ----- Session management -----
        Tool(
            name="list_sessions",
            description=(
                "List all deliberation sessions (projects) on the Friction server. "
                "Shows session ID, title, status, and ticket count. "
                "Call this first to see which projects are available, then use "
                "`use_session` to pick one."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="use_session",
            description=(
                "Set the active session/project. After calling this, all ticket tools "
                "automatically use this session — you don't need to pass session_id. "
                "Use `list_sessions` first to see available sessions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "The session ID to activate. Get this from list_sessions.",
                    },
                },
                "required": ["session_id"],
            },
        ),
        Tool(
            name="get_next_ticket",
            description=(
                "Get and atomically claim the next available ticket. "
                "Returns the ticket with full description, acceptance criteria, "
                "files to create/modify, and dependency outputs from completed tickets. "
                "No other agent will receive the same ticket. "
                "Uses the active session unless session_id is provided."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Optional — overrides the active session.",
                    },
                    "agent_role": {
                        "type": "string",
                        "description": (
                            "Optional role filter: 'backend', 'frontend', 'database', "
                            "'devops', 'qa', 'docs', 'fullstack'."
                        ),
                    },
                },
            },
        ),
        Tool(
            name="mark_done",
            description=(
                "Mark a ticket as completed. You MUST provide an output_summary "
                "describing what you built, files created/modified, key decisions, "
                "any bugs or workarounds, and how to test it. "
                "This summary is passed to downstream tickets that depend on yours."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "The ticket ID (e.g. FRIC-A1B2C3)."},
                    "output_summary": {
                        "type": "string",
                        "description": (
                            "Summary of what was implemented. Include: files created/modified, "
                            "key decisions, known issues, and how to test."
                        ),
                    },
                },
                "required": ["ticket_id", "output_summary"],
            },
        ),
        Tool(
            name="fail_ticket",
            description="Mark a ticket as failed with an error description.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "The ticket ID."},
                    "error": {"type": "string", "description": "Why the ticket failed."},
                },
                "required": ["ticket_id", "error"],
            },
        ),
        Tool(
            name="list_tickets",
            description=(
                "List all tickets for the active session grouped by status. "
                "Uses the active session unless session_id is provided."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Optional — overrides the active session.",
                    },
                },
            },
        ),
        Tool(
            name="get_ticket_context",
            description=(
                "Get a specific ticket with all completed dependency output summaries. "
                "Use this to understand the full context before working on a ticket."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "The ticket ID."},
                },
                "required": ["ticket_id"],
            },
        ),
        Tool(
            name="get_status",
            description=(
                "Get the current board status — ticket counts, progress percentage. "
                "Uses the active session unless session_id is provided."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Optional — overrides the active session.",
                    },
                },
            },
        ),
        Tool(
            name="get_workflow",
            description=(
                "Get the full dependency graph as ReactFlow nodes and edges. "
                "Uses the active session unless session_id is provided."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Optional — overrides the active session.",
                    },
                },
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    global _active_session_id, _active_session_title

    async with aiohttp.ClientSession() as http:
        try:
            # ----- Deliberation tools -----

            if name == "start_deliberation":
                idea = arguments["idea"]

                # Create session on the server
                resp = await http.post(
                    f"{FRICTION_API_URL}/sessions/",
                    json={"idea": idea},
                )
                resp.raise_for_status()
                session = await resp.json()

                sid = session["id"]
                title = session.get("title", "Untitled")

                # Set as active session
                _active_session_id = sid
                _active_session_title = title

                # Open dashboard in browser
                dashboard_url = f"{FRICTION_DASHBOARD_URL}"
                try:
                    webbrowser.open(dashboard_url)
                except Exception:
                    pass  # browser open is best-effort

                return [TextContent(
                    type="text",
                    text=(
                        f"Deliberation started!\n\n"
                        f"**Session**: {title}\n"
                        f"**ID**: `{sid}`\n\n"
                        f"The Friction dashboard has opened in your browser at:\n"
                        f"{dashboard_url}\n\n"
                        f"**What to do now:**\n"
                        f"1. Go to the browser — Friction AI is already challenging your idea\n"
                        f"2. Answer its questions, debate back and forth\n"
                        f"3. When satisfied, click 'Complete' to generate tickets\n"
                        f"4. Come back here and say 'ready' or 'done' — I'll fetch the prompt and start implementing\n\n"
                        f"Session is saved as active. When you return, I'll call `get_agent_prompt` "
                        f"to get the full context and start working on tickets."
                    ),
                )]

            elif name == "get_agent_prompt":
                sid = _resolve_session(arguments) or _active_session_id
                if not sid:
                    return [TextContent(
                        type="text",
                        text="No active session. Call `start_deliberation` or `use_session` first.",
                    )]

                resp = await http.get(f"{FRICTION_API_URL}/sessions/{sid}/agent-prompt")
                if resp.status == 404:
                    return [TextContent(
                        type="text",
                        text=(
                            "No agent prompt available yet. The deliberation may not be complete.\n"
                            "Go to the Friction dashboard and click 'Complete' to finish deliberation "
                            "and generate tickets."
                        ),
                    )]
                resp.raise_for_status()
                data = await resp.json()
                return [TextContent(type="text", text=data["prompt"])]

            # ----- Session management -----

            elif name == "list_sessions":
                resp = await http.get(f"{FRICTION_API_URL}/sessions/")
                resp.raise_for_status()
                sessions = await resp.json()

                if not sessions:
                    return [TextContent(type="text", text="No sessions found. Create one in the Friction UI first.")]

                lines = ["# Friction Sessions\n"]
                if _active_session_id:
                    lines.append(f"**Active session**: {_active_session_title} (`{_active_session_id}`)\n")
                else:
                    lines.append("**No active session** — call `use_session` with a session ID below.\n")

                for s in sessions:
                    status_icon = {"deliberating": "💬", "completed": "✅"}.get(s.get("status", ""), "❓")
                    sid = s["id"]
                    title = s.get("title", "Untitled")
                    status = s.get("status", "unknown")
                    idea = s.get("idea", "")[:100]
                    active_mark = " ← ACTIVE" if sid == _active_session_id else ""
                    lines.append(f"### {status_icon} {title}{active_mark}")
                    lines.append(f"- **ID**: `{sid}`")
                    lines.append(f"- **Status**: {status}")
                    if idea:
                        lines.append(f"- **Idea**: {idea}")
                    lines.append("")

                lines.append("---")
                lines.append("Call `use_session` with the session ID you want to work on.")

                return [TextContent(type="text", text="\n".join(lines))]

            elif name == "use_session":
                sid = arguments["session_id"]
                # Validate the session exists
                resp = await http.get(f"{FRICTION_API_URL}/sessions/{sid}")
                if resp.status == 404:
                    return [TextContent(type="text", text=f"Session `{sid}` not found. Use `list_sessions` to see available sessions.")]
                resp.raise_for_status()
                session = await resp.json()

                _active_session_id = sid
                _active_session_title = session.get("title", "Untitled")

                return [TextContent(
                    type="text",
                    text=(
                        f"Active session set to: **{_active_session_title}**\n"
                        f"Session ID: `{sid}`\n"
                        f"Status: {session.get('status', 'unknown')}\n\n"
                        f"All ticket tools will now use this session automatically. "
                        f"You can call `get_next_ticket` to start working."
                    ),
                )]

            # ----- Ticket tools -----

            elif name == "get_next_ticket":
                sid = _require_session(arguments)
                resp = await http.post(
                    f"{FRICTION_API_URL}/sessions/{sid}/tickets/next",
                    json={"agent_role": arguments.get("agent_role")},
                )
                if resp.status == 404:
                    return [TextContent(type="text", text="No tickets available. All done or all blocked.")]
                if resp.status >= 400:
                    detail = await resp.text()
                    return [TextContent(type="text", text=f"Error fetching ticket (HTTP {resp.status}): {detail}")]
                data = await resp.json()
                return [TextContent(
                    type="text",
                    text=_format_ticket(data["ticket"], data.get("dependency_outputs")),
                )]

            elif name == "mark_done":
                resp = await http.patch(
                    f"{FRICTION_API_URL}/tickets/{arguments['ticket_id']}",
                    json={
                        "status": "completed",
                        "output_summary": arguments["output_summary"],
                    },
                )
                resp.raise_for_status()
                return [TextContent(
                    type="text",
                    text=f"Ticket {arguments['ticket_id']} marked as COMPLETED. Downstream dependents may now be unblocked.",
                )]

            elif name == "fail_ticket":
                resp = await http.patch(
                    f"{FRICTION_API_URL}/tickets/{arguments['ticket_id']}",
                    json={
                        "status": "failed",
                        "output_summary": arguments["error"],
                    },
                )
                resp.raise_for_status()
                return [TextContent(
                    type="text",
                    text=f"Ticket {arguments['ticket_id']} marked as FAILED: {arguments['error']}",
                )]

            elif name == "list_tickets":
                sid = _require_session(arguments)
                resp = await http.get(f"{FRICTION_API_URL}/sessions/{sid}/tickets")
                resp.raise_for_status()
                tickets = await resp.json()

                if not tickets:
                    return [TextContent(type="text", text="No tickets found for this session.")]

                lines = [f"# Friction Board — {_active_session_title or sid}\n"]
                by_status: dict[str, list] = {}
                for t in tickets:
                    by_status.setdefault(t["status"], []).append(t)

                for status in ["ready", "in_progress", "blocked", "completed", "failed"]:
                    group = by_status.get(status, [])
                    if not group:
                        continue
                    lines.append(f"## {status.upper()} ({len(group)})")
                    for t in group:
                        active = "" if t.get("active", True) else " [PAUSED]"
                        source = f" (Issue: {t['source_issue_title']})" if t.get("source_issue_title") else ""
                        lines.append(
                            f"- **{t['id']}**: {t['title']} "
                            f"({t['domain']}, L{t['layer']}, P{t.get('priority', '?')}){source}{active}"
                        )
                    lines.append("")

                return [TextContent(type="text", text="\n".join(lines))]

            elif name == "get_ticket_context":
                resp = await http.get(
                    f"{FRICTION_API_URL}/tickets/{arguments['ticket_id']}/context"
                )
                resp.raise_for_status()
                data = await resp.json()
                return [TextContent(
                    type="text",
                    text=_format_ticket(data["ticket"], data.get("dependency_outputs")),
                )]

            elif name == "get_status":
                sid = _require_session(arguments)
                resp = await http.get(f"{FRICTION_API_URL}/sessions/{sid}/status")
                resp.raise_for_status()
                data = await resp.json()
                lines = [
                    f"# Board Status — {_active_session_title or sid}",
                    f"- **Total**: {data['total']}",
                    f"- **Completed**: {data['completed']}",
                    f"- **In Progress**: {data['in_progress']}",
                    f"- **Ready**: {data['ready']}",
                    f"- **Blocked**: {data['blocked']}",
                    f"- **Failed**: {data['failed']}",
                    f"- **Progress**: {data['percent_complete']}%",
                ]
                return [TextContent(type="text", text="\n".join(lines))]

            elif name == "get_workflow":
                sid = _require_session(arguments)
                resp = await http.get(f"{FRICTION_API_URL}/sessions/{sid}/workflow")
                resp.raise_for_status()
                return [TextContent(type="text", text=json.dumps(await resp.json(), indent=2))]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except ValueError as e:
            return [TextContent(type="text", text=str(e))]
        except aiohttp.ClientError as e:
            return [TextContent(type="text", text=f"Error calling Friction API: {e}")]
        except Exception as e:
            logger.exception("Tool call failed: %s", name)
            return [TextContent(type="text", text=f"Error: {e}")]


async def main():
    """Run the MCP server on stdio."""
    logger.info("Starting Friction MCP server (API: %s)", FRICTION_API_URL)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
