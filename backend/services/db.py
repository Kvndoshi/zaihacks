"""SQLite persistence layer using aiosqlite with automatic JSON serde.

Each column is stored individually (not as a JSON blob) so the schema is
queryable.  List/dict fields are serialised to JSON text columns.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

from backend.config import config
from backend.models.codebase import (
    ArchitecturePattern,
    CodebaseAnalysis,
    FileInfo,
    GitHubIssue,
    GitHubLabel,
    IssueType,
    TechStackInfo,
)
from backend.models.session import DeliberationSession, SessionMessage
from backend.models.ticket import Ticket

# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def _serialise_json(value: list | dict) -> str:
    """Dump a list/dict to a JSON string for storage."""
    return json.dumps(value, default=str)


def _deserialise_json(raw: str | None) -> list | dict:
    """Parse a JSON string back; returns empty list on ``None``/empty."""
    if not raw:
        return []
    return json.loads(raw)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------


async def _get_db() -> aiosqlite.Connection:
    db_path = Path(config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """Create tables if they don't already exist."""
    db = await _get_db()
    try:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id              TEXT PRIMARY KEY,
                title           TEXT NOT NULL,
                idea            TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'deliberating',
                messages        TEXT NOT NULL DEFAULT '[]',
                key_insights    TEXT NOT NULL DEFAULT '[]',
                risks           TEXT NOT NULL DEFAULT '[]',
                refined_idea    TEXT,
                codebase_id     TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id                  TEXT PRIMARY KEY,
                session_id          TEXT NOT NULL,
                title               TEXT NOT NULL,
                description         TEXT NOT NULL,
                layer               INTEGER NOT NULL,
                domain              TEXT NOT NULL,
                priority            INTEGER NOT NULL DEFAULT 2,
                status              TEXT NOT NULL DEFAULT 'blocked',
                depends_on          TEXT NOT NULL DEFAULT '[]',
                blocks              TEXT NOT NULL DEFAULT '[]',
                acceptance_criteria TEXT NOT NULL DEFAULT '[]',
                files_to_create     TEXT NOT NULL DEFAULT '[]',
                files_to_modify     TEXT NOT NULL DEFAULT '[]',
                output_summary      TEXT,
                agent_id            TEXT,
                claimed_at          TEXT,
                completed_at        TEXT,
                created_at          TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS codebase_analyses (
                id                      TEXT PRIMARY KEY,
                session_id              TEXT,
                repo_url                TEXT,
                tech_stack              TEXT NOT NULL DEFAULT '{}',
                architecture_patterns   TEXT NOT NULL DEFAULT '[]',
                key_files               TEXT NOT NULL DEFAULT '[]',
                summary                 TEXT NOT NULL DEFAULT '',
                file_count              INTEGER NOT NULL DEFAULT 0,
                total_size              INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS github_issues (
                id              TEXT PRIMARY KEY,
                analysis_id     TEXT NOT NULL,
                github_id       INTEGER,
                title           TEXT,
                body            TEXT DEFAULT '',
                state           TEXT DEFAULT 'open',
                labels          TEXT DEFAULT '[]',
                issue_type      TEXT DEFAULT 'other',
                html_url        TEXT DEFAULT '',
                created_at      TEXT DEFAULT '',
                FOREIGN KEY (analysis_id) REFERENCES codebase_analyses(id)
            );
            """
        )

        # Add new columns to tickets table (safe for existing DBs)
        for col, default in [
            ("source_issue_id", "NULL"),
            ("source_issue_title", "NULL"),
            ("active", "1"),
        ]:
            try:
                await db.execute(
                    f"ALTER TABLE tickets ADD COLUMN {col} TEXT DEFAULT {default}"
                )
            except Exception:
                pass  # Column already exists

        # Add agent_prompt column to sessions (safe for existing DBs)
        try:
            await db.execute("ALTER TABLE sessions ADD COLUMN agent_prompt TEXT DEFAULT NULL")
        except Exception:
            pass

        # Add codebase_index column to codebase_analyses (safe for existing DBs)
        try:
            await db.execute(
                "ALTER TABLE codebase_analyses ADD COLUMN codebase_index TEXT DEFAULT NULL"
            )
        except Exception:
            pass

        await db.commit()
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Sessions CRUD
# ---------------------------------------------------------------------------


async def save_session(session: DeliberationSession) -> DeliberationSession:
    """Insert or replace a full session row."""
    db = await _get_db()
    try:
        messages_json = _serialise_json(
            [m.model_dump(mode="json") for m in session.messages]
        )
        await db.execute(
            """
            INSERT OR REPLACE INTO sessions
                (id, title, idea, status, messages, key_insights, risks,
                 refined_idea, codebase_id, agent_prompt, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.title,
                session.idea,
                session.status.value,
                messages_json,
                _serialise_json(session.key_insights),
                _serialise_json(session.risks),
                session.refined_idea,
                session.codebase_id,
                session.agent_prompt,
                session.created_at.isoformat(),
                _now_iso(),
            ),
        )
        await db.commit()
    finally:
        await db.close()
    return session


async def get_session(session_id: str) -> Optional[DeliberationSession]:
    """Fetch a single session by id, or ``None``."""
    db = await _get_db()
    try:
        cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_session(row)
    finally:
        await db.close()


async def list_sessions() -> list[DeliberationSession]:
    """Return all sessions ordered newest-first."""
    db = await _get_db()
    try:
        cursor = await db.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [_row_to_session(r) for r in rows]
    finally:
        await db.close()


def _row_to_session(row: aiosqlite.Row) -> DeliberationSession:
    raw_messages = _deserialise_json(row["messages"])
    messages = [SessionMessage.model_validate(m) for m in raw_messages]
    # Handle missing agent_prompt column for older DBs
    agent_prompt = None
    try:
        agent_prompt = row["agent_prompt"]
    except (IndexError, KeyError):
        pass
    return DeliberationSession(
        id=row["id"],
        title=row["title"],
        idea=row["idea"],
        status=row["status"],
        messages=messages,
        key_insights=_deserialise_json(row["key_insights"]),
        risks=_deserialise_json(row["risks"]),
        refined_idea=row["refined_idea"],
        codebase_id=row["codebase_id"],
        agent_prompt=agent_prompt,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Tickets CRUD
# ---------------------------------------------------------------------------


async def save_ticket(ticket: Ticket) -> Ticket:
    """Insert or replace a full ticket row."""
    db = await _get_db()
    try:
        await db.execute(
            """
            INSERT OR REPLACE INTO tickets
                (id, session_id, title, description, layer, domain, priority,
                 status, depends_on, blocks, acceptance_criteria,
                 files_to_create, files_to_modify, output_summary,
                 agent_id, source_issue_id, source_issue_title, active,
                 claimed_at, completed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket.id,
                ticket.session_id,
                ticket.title,
                ticket.description,
                ticket.layer,
                ticket.domain.value,
                ticket.priority.value,
                ticket.status.value,
                _serialise_json(ticket.depends_on),
                _serialise_json(ticket.blocks),
                _serialise_json(ticket.acceptance_criteria),
                _serialise_json(ticket.files_to_create),
                _serialise_json(ticket.files_to_modify),
                ticket.output_summary,
                ticket.agent_id,
                ticket.source_issue_id,
                ticket.source_issue_title,
                1 if ticket.active else 0,
                ticket.claimed_at.isoformat() if ticket.claimed_at else None,
                ticket.completed_at.isoformat() if ticket.completed_at else None,
                ticket.created_at.isoformat(),
            ),
        )
        await db.commit()
    finally:
        await db.close()
    return ticket


async def get_ticket(ticket_id: str) -> Optional[Ticket]:
    """Fetch a single ticket by id."""
    db = await _get_db()
    try:
        cursor = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_ticket(row)
    finally:
        await db.close()


async def get_tickets_by_session(session_id: str) -> list[Ticket]:
    """Return all tickets for a session, ordered by layer then priority."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM tickets WHERE session_id = ? ORDER BY layer, priority",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_ticket(r) for r in rows]
    finally:
        await db.close()


async def delete_ticket(ticket_id: str) -> bool:
    """Delete a ticket from the database. Returns True if a row was removed."""
    db = await _get_db()
    try:
        cursor = await db.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def update_ticket(ticket_id: str, **kwargs) -> Optional[Ticket]:
    """Partial update — pass only the fields you want to change."""
    ticket = await get_ticket(ticket_id)
    if ticket is None:
        return None

    update_data = ticket.model_dump()
    update_data.update(kwargs)
    updated = Ticket.model_validate(update_data)
    return await save_ticket(updated)


def _row_to_ticket(row: aiosqlite.Row) -> Ticket:
    # Handle columns that may not exist in older DBs
    keys = row.keys() if hasattr(row, "keys") else []
    return Ticket(
        id=row["id"],
        session_id=row["session_id"],
        title=row["title"],
        description=row["description"],
        layer=row["layer"],
        domain=row["domain"],
        priority=row["priority"],
        status=row["status"],
        depends_on=_deserialise_json(row["depends_on"]),
        blocks=_deserialise_json(row["blocks"]),
        acceptance_criteria=_deserialise_json(row["acceptance_criteria"]),
        files_to_create=_deserialise_json(row["files_to_create"]),
        files_to_modify=_deserialise_json(row["files_to_modify"]),
        output_summary=row["output_summary"],
        agent_id=row["agent_id"],
        source_issue_id=row["source_issue_id"] if "source_issue_id" in keys else None,
        source_issue_title=row["source_issue_title"] if "source_issue_title" in keys else None,
        active=bool(row["active"]) if "active" in keys and row["active"] is not None else True,
        claimed_at=row["claimed_at"],
        completed_at=row["completed_at"],
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# Codebase analyses CRUD
# ---------------------------------------------------------------------------


async def save_codebase_analysis(analysis: CodebaseAnalysis) -> CodebaseAnalysis:
    """Insert or replace a codebase analysis row."""
    db = await _get_db()
    try:
        await db.execute(
            """
            INSERT OR REPLACE INTO codebase_analyses
                (id, session_id, repo_url, tech_stack, architecture_patterns,
                 key_files, summary, file_count, total_size, codebase_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                analysis.id,
                analysis.session_id,
                analysis.repo_url,
                _serialise_json(analysis.tech_stack.model_dump()),
                _serialise_json(
                    [p.model_dump() for p in analysis.architecture_patterns]
                ),
                _serialise_json([f.model_dump() for f in analysis.key_files]),
                analysis.summary,
                analysis.file_count,
                analysis.total_size,
                analysis.codebase_index,
            ),
        )
        await db.commit()
    finally:
        await db.close()
    return analysis


async def get_codebase_analysis(
    analysis_id: str,
) -> Optional[CodebaseAnalysis]:
    """Fetch a codebase analysis by id."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM codebase_analyses WHERE id = ?", (analysis_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_analysis(row)
    finally:
        await db.close()


async def update_session(session: DeliberationSession) -> DeliberationSession:
    """Alias for save_session — upserts the session row."""
    return await save_session(session)


def _row_to_analysis(row: aiosqlite.Row) -> CodebaseAnalysis:
    tech_stack_raw = _deserialise_json(row["tech_stack"])
    if isinstance(tech_stack_raw, dict):
        tech_stack = TechStackInfo.model_validate(tech_stack_raw)
    else:
        tech_stack = TechStackInfo()

    patterns_raw = _deserialise_json(row["architecture_patterns"])
    patterns = [ArchitecturePattern.model_validate(p) for p in patterns_raw]

    files_raw = _deserialise_json(row["key_files"])
    key_files = [FileInfo.model_validate(f) for f in files_raw]

    # Handle missing codebase_index column for older DBs
    codebase_index = None
    try:
        codebase_index = row["codebase_index"]
    except (IndexError, KeyError):
        pass

    return CodebaseAnalysis(
        id=row["id"],
        session_id=row["session_id"],
        repo_url=row["repo_url"],
        tech_stack=tech_stack,
        architecture_patterns=patterns,
        key_files=key_files,
        summary=row["summary"],
        file_count=row["file_count"],
        total_size=row["total_size"],
        codebase_index=codebase_index,
    )


# ---------------------------------------------------------------------------
# GitHub Issues CRUD
# ---------------------------------------------------------------------------


async def save_github_issues(
    analysis_id: str, issues: list[GitHubIssue]
) -> list[GitHubIssue]:
    """Bulk-insert GitHub issues linked to a codebase analysis."""
    db = await _get_db()
    try:
        for iss in issues:
            labels_json = _serialise_json([lbl.model_dump() for lbl in iss.labels])
            await db.execute(
                """
                INSERT OR REPLACE INTO github_issues
                    (id, analysis_id, github_id, title, body, state,
                     labels, issue_type, html_url, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    iss.id,
                    analysis_id,
                    iss.github_id,
                    iss.title,
                    iss.body,
                    iss.state,
                    labels_json,
                    iss.issue_type.value,
                    iss.html_url,
                    iss.created_at,
                ),
            )
        await db.commit()
    finally:
        await db.close()
    return issues


async def get_github_issues(analysis_id: str) -> list[GitHubIssue]:
    """Fetch all GitHub issues for a codebase analysis."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM github_issues WHERE analysis_id = ? ORDER BY github_id",
            (analysis_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_github_issue(r) for r in rows]
    finally:
        await db.close()


async def get_github_issues_by_ids(issue_ids: list[str]) -> list[GitHubIssue]:
    """Fetch specific GitHub issues by their internal IDs."""
    if not issue_ids:
        return []
    db = await _get_db()
    try:
        placeholders = ",".join("?" for _ in issue_ids)
        cursor = await db.execute(
            f"SELECT * FROM github_issues WHERE id IN ({placeholders})",
            issue_ids,
        )
        rows = await cursor.fetchall()
        return [_row_to_github_issue(r) for r in rows]
    finally:
        await db.close()


def _row_to_github_issue(row: aiosqlite.Row) -> GitHubIssue:
    labels_raw = _deserialise_json(row["labels"])
    labels = [GitHubLabel.model_validate(lbl) for lbl in labels_raw]
    return GitHubIssue(
        id=row["id"],
        github_id=row["github_id"],
        title=row["title"],
        body=row["body"] or "",
        state=row["state"] or "open",
        labels=labels,
        issue_type=row["issue_type"] or "other",
        html_url=row["html_url"] or "",
        created_at=row["created_at"] or "",
    )
