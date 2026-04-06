"""TicketManager — central orchestrator for ticket lifecycle operations."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from backend.models.ticket import Ticket, TicketDomain, TicketStatus
from backend.models.workflow import WorkflowGraph
from backend.services import db as db_service
from backend.tickets.dependency_graph import DependencyGraphBuilder

logger = logging.getLogger(__name__)

# Keywords that signal a dependency output contains issues
_BUG_KEYWORDS = re.compile(
    r"\b(bug|issue|error|known issue|workaround|hack|todo|fixme|"
    r"broken|regression|fails?|failing|crash|exception)\b",
    re.IGNORECASE,
)

# Domain-to-role heuristic mapping
_ROLE_DOMAIN_MAP: dict[str, list[TicketDomain]] = {
    "backend": [TicketDomain.BACKEND, TicketDomain.API, TicketDomain.AUTH],
    "frontend": [TicketDomain.FRONTEND],
    "database": [TicketDomain.DATABASE],
    "devops": [TicketDomain.INFRA],
    "qa": [TicketDomain.TESTING],
    "docs": [TicketDomain.DOCS],
    "marketing": [TicketDomain.MARKETING, TicketDomain.CONTENT],
    "design": [TicketDomain.DESIGN],
    "research": [TicketDomain.RESEARCH],
    "operations": [TicketDomain.OPERATIONS],
    "legal": [TicketDomain.LEGAL],
    "business": [TicketDomain.BUSINESS],
    "general": [TicketDomain.GENERAL],
    "fullstack": list(TicketDomain),
}


class TicketManager:
    """Central orchestrator for ticket CRUD, claiming, completion, and
    dependency-aware status transitions."""

    def __init__(self, llm_client, db=None):
        self.llm = llm_client
        self.db = db or db_service
        self.graph_builder = DependencyGraphBuilder()
        self._lock = asyncio.Lock()
        # In-memory cache: session_id -> {ticket_id -> Ticket}
        self._tickets: dict[str, dict[str, Ticket]] = {}

    # ------------------------------------------------------------------
    # Ticket creation
    # ------------------------------------------------------------------

    async def create_tickets(
        self, session_id: str, tickets: list[Ticket]
    ) -> list[Ticket]:
        """Store generated tickets.  Set initial statuses and persist."""
        session_tickets: dict[str, Ticket] = {}

        for t in tickets:
            t.session_id = session_id
            # Tickets with no deps -> READY, others -> BLOCKED
            if not t.depends_on:
                t.status = TicketStatus.READY
            else:
                t.status = TicketStatus.BLOCKED
            session_tickets[t.id] = t
            await self.db.save_ticket(t)

        self._tickets[session_id] = session_tickets
        logger.info(
            "Created %d tickets for session %s", len(tickets), session_id
        )
        return tickets

    # ------------------------------------------------------------------
    # Ticket deletion
    # ------------------------------------------------------------------

    async def delete_ticket(
        self, session_id: str, ticket_id: str
    ) -> bool:
        """Remove a ticket, clean up dependency references, and re-check blocked tickets."""
        async with self._lock:
            await self._load_session_tickets(session_id)
            store = self._tickets.get(session_id, {})

            if ticket_id not in store:
                return False

            # Remove from cache
            del store[ticket_id]

            # Remove from DB
            await self.db.delete_ticket(ticket_id)

            # Clean up: remove ticket_id from other tickets' depends_on and blocks
            for t in store.values():
                changed = False
                if ticket_id in t.depends_on:
                    t.depends_on.remove(ticket_id)
                    changed = True
                if ticket_id in t.blocks:
                    t.blocks.remove(ticket_id)
                    changed = True

                # If ticket was BLOCKED and now all remaining deps are completed, promote to READY
                if changed and t.status == TicketStatus.BLOCKED:
                    all_done = all(
                        store.get(dep_id, t).status == TicketStatus.COMPLETED
                        for dep_id in t.depends_on
                    ) if t.depends_on else True
                    if all_done:
                        t.status = TicketStatus.READY
                        logger.info("Ticket %s unblocked after deletion → READY", t.id)

                if changed:
                    await self.db.save_ticket(t)

            logger.info("Deleted ticket %s from session %s", ticket_id, session_id)
            return True

    # ------------------------------------------------------------------
    # Ticket retrieval / claiming
    # ------------------------------------------------------------------

    async def get_next_ticket(
        self,
        session_id: str,
        agent_role: str | None = None,
    ) -> Optional[dict[str, Any]]:
        """Atomically find and claim the next available ticket.

        Args:
            session_id: The session to look in.
            agent_role: Optional role string (e.g. "backend", "frontend").
                        When provided, tickets are filtered to domains that
                        match the role.

        Returns:
            ``{"ticket": Ticket, "dependency_outputs": {dep_id: summary}}``
            or ``None`` if no tickets are available.
        """
        async with self._lock:
            await self._load_session_tickets(session_id)
            store = self._tickets.get(session_id, {})
            if not store:
                return None

            # Determine eligible domains for this role
            eligible_domains: set[TicketDomain] | None = None
            if agent_role:
                role_key = agent_role.lower().strip()
                domains = _ROLE_DOMAIN_MAP.get(role_key)
                if domains:
                    eligible_domains = set(domains)

            # Filter to READY + active tickets
            ready: list[Ticket] = [
                t for t in store.values()
                if t.status == TicketStatus.READY
                and t.active
                and (eligible_domains is None or t.domain in eligible_domains)
            ]

            if not ready:
                return None

            # Sort by layer ascending, then priority ascending (0=CRITICAL first)
            ready.sort(key=lambda t: (t.layer, t.priority.value))
            ticket = ready[0]

            # Bug-aware check: patch description if deps reported issues
            # Non-blocking — skip if LLM fails (e.g. rate limit)
            try:
                ticket = await self._check_for_bugs(ticket, session_id)
            except Exception:
                logger.warning("Bug-check skipped for %s (LLM unavailable)", ticket.id)

            # Claim the ticket
            ticket.status = TicketStatus.IN_PROGRESS
            ticket.claimed_at = datetime.now(timezone.utc)
            store[ticket.id] = ticket
            await self.db.save_ticket(ticket)

            # Gather dependency outputs
            dep_outputs = self._gather_dependency_outputs(ticket, store)

            return {"ticket": ticket, "dependency_outputs": dep_outputs}

    async def claim_ticket(
        self, session_id: str, ticket_id: str, agent_id: str
    ) -> Ticket:
        """Claim a specific ticket by ID."""
        async with self._lock:
            await self._load_session_tickets(session_id)
            store = self._tickets.get(session_id, {})
            ticket = store.get(ticket_id)
            if ticket is None:
                raise ValueError(f"Ticket {ticket_id} not found in session {session_id}")
            if ticket.status != TicketStatus.READY:
                raise ValueError(
                    f"Ticket {ticket_id} is {ticket.status.value}, not READY"
                )

            ticket.status = TicketStatus.IN_PROGRESS
            ticket.agent_id = agent_id
            ticket.claimed_at = datetime.now(timezone.utc)
            store[ticket_id] = ticket
            await self.db.save_ticket(ticket)
            return ticket

    # ------------------------------------------------------------------
    # Ticket completion / failure
    # ------------------------------------------------------------------

    async def complete_ticket(
        self, session_id: str, ticket_id: str, output_summary: str
    ) -> Ticket:
        """Mark a ticket as completed and unlock dependents.

        After marking the ticket COMPLETED this method checks every
        ticket that depends on it.  If *all* of a dependent ticket's
        dependencies are now COMPLETED, that dependent is promoted from
        BLOCKED to READY.
        """
        async with self._lock:
            await self._load_session_tickets(session_id)
            store = self._tickets.get(session_id, {})
            ticket = store.get(ticket_id)
            if ticket is None:
                raise ValueError(f"Ticket {ticket_id} not found")

            ticket.status = TicketStatus.COMPLETED
            ticket.output_summary = output_summary
            ticket.completed_at = datetime.now(timezone.utc)
            store[ticket_id] = ticket
            await self.db.save_ticket(ticket)

            # Unlock dependents
            unlocked = self._unlock_dependents(ticket_id, store)
            for ut in unlocked:
                await self.db.save_ticket(ut)

            logger.info(
                "Completed ticket %s; unlocked %d dependents",
                ticket_id,
                len(unlocked),
            )
            return ticket

    async def fail_ticket(
        self, session_id: str, ticket_id: str, error: str
    ) -> Ticket:
        """Mark a ticket as failed with an error message."""
        async with self._lock:
            await self._load_session_tickets(session_id)
            store = self._tickets.get(session_id, {})
            ticket = store.get(ticket_id)
            if ticket is None:
                raise ValueError(f"Ticket {ticket_id} not found")

            ticket.status = TicketStatus.FAILED
            ticket.output_summary = f"FAILED: {error}"
            ticket.completed_at = datetime.now(timezone.utc)
            store[ticket_id] = ticket
            await self.db.save_ticket(ticket)

            logger.warning("Ticket %s failed: %s", ticket_id, error)
            return ticket

    # ------------------------------------------------------------------
    # Context & board state
    # ------------------------------------------------------------------

    async def get_ticket_context(
        self, session_id: str, ticket_id: str
    ) -> dict[str, Any]:
        """Return a ticket together with all completed dependency output summaries.

        Returns:
            ``{"ticket": Ticket, "dependency_outputs": {dep_id: summary}}``
        """
        await self._load_session_tickets(session_id)
        store = self._tickets.get(session_id, {})
        ticket = store.get(ticket_id)
        if ticket is None:
            raise ValueError(f"Ticket {ticket_id} not found")

        dep_outputs = self._gather_dependency_outputs(ticket, store)
        return {"ticket": ticket, "dependency_outputs": dep_outputs}

    async def get_board_state(self, session_id: str) -> dict[str, Any]:
        """Return the full board state for the dashboard.

        Returns:
            ``{"tickets": [...], "stats": {...}}``
        """
        await self._load_session_tickets(session_id)
        store = self._tickets.get(session_id, {})
        tickets = list(store.values())

        total = len(tickets)
        completed = sum(1 for t in tickets if t.status == TicketStatus.COMPLETED)
        in_progress = sum(1 for t in tickets if t.status == TicketStatus.IN_PROGRESS)
        blocked = sum(1 for t in tickets if t.status == TicketStatus.BLOCKED)
        ready = sum(1 for t in tickets if t.status == TicketStatus.READY)
        failed = sum(1 for t in tickets if t.status == TicketStatus.FAILED)

        percent_complete = (completed / total * 100) if total > 0 else 0.0

        return {
            "tickets": [t.model_dump(mode="json") for t in tickets],
            "stats": {
                "total": total,
                "completed": completed,
                "in_progress": in_progress,
                "blocked": blocked,
                "ready": ready,
                "failed": failed,
                "percent_complete": round(percent_complete, 1),
            },
        }

    async def get_workflow(self, session_id: str) -> WorkflowGraph:
        """Build and return a ReactFlow-compatible workflow graph."""
        await self._load_session_tickets(session_id)
        store = self._tickets.get(session_id, {})
        tickets = list(store.values())
        return self.graph_builder.build_graph(tickets)

    # ------------------------------------------------------------------
    # Issue group activation
    # ------------------------------------------------------------------

    async def set_issue_group_active(
        self, session_id: str, source_issue_id: str, active: bool
    ) -> list[Ticket]:
        """Bulk-toggle all tickets sharing the given source_issue_id."""
        async with self._lock:
            await self._load_session_tickets(session_id)
            store = self._tickets.get(session_id, {})
            updated: list[Ticket] = []

            for t in store.values():
                if t.source_issue_id == source_issue_id:
                    t.active = active
                    store[t.id] = t
                    await self.db.save_ticket(t)
                    updated.append(t)

            logger.info(
                "Set %d tickets for issue %s to active=%s",
                len(updated), source_issue_id, active,
            )
            return updated

    # ------------------------------------------------------------------
    # Bug-aware patching
    # ------------------------------------------------------------------

    async def _check_for_bugs(
        self, ticket: Ticket, session_id: str
    ) -> Ticket:
        """Inspect completed dependency outputs for bug signals.

        If any dependency output mentions bugs, errors, or known issues,
        call the LLM to generate a warning note that is prepended to the
        ticket description so the implementing agent is aware.
        """
        store = self._tickets.get(session_id, {})
        bug_reports: list[str] = []

        for dep_id in ticket.depends_on:
            dep = store.get(dep_id)
            if dep and dep.output_summary and _BUG_KEYWORDS.search(dep.output_summary):
                bug_reports.append(f"[{dep_id}] {dep.output_summary}")

        if not bug_reports:
            return ticket

        logger.info(
            "Bug signals found in deps of %s; patching description", ticket.id
        )

        bug_context = "\n".join(bug_reports)
        prompt = (
            f"The following dependency tickets reported issues:\n\n"
            f"{bug_context}\n\n"
            f"The next ticket to be worked on is:\n"
            f"Title: {ticket.title}\n"
            f"Description: {ticket.description}\n\n"
            f"Write a SHORT (2-4 sentence) warning note for the developer "
            f"implementing this ticket, summarizing the upstream issues they "
            f"should be aware of and any adjustments they should make. "
            f"Respond with ONLY the warning note text."
        )

        try:
            note = await self.llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="You are a helpful engineering lead.",
                temperature=0.3,
            )
            ticket.description = (
                f"⚠️ UPSTREAM ISSUE NOTICE:\n{note.strip()}\n\n"
                f"---\n\n{ticket.description}"
            )
        except Exception:
            logger.exception("Failed to generate bug-aware patch for %s", ticket.id)

        return ticket

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _unlock_dependents(
        self, completed_id: str, store: dict[str, Ticket]
    ) -> list[Ticket]:
        """Check tickets that depend on *completed_id* and promote them
        to READY if all their dependencies are now COMPLETED.

        Returns the list of tickets whose status was changed.
        """
        unlocked: list[Ticket] = []
        for t in store.values():
            if t.status != TicketStatus.BLOCKED:
                continue
            if completed_id not in t.depends_on:
                continue

            all_done = all(
                store.get(dep_id, t).status == TicketStatus.COMPLETED
                for dep_id in t.depends_on
            )
            if all_done:
                t.status = TicketStatus.READY
                store[t.id] = t
                unlocked.append(t)
                logger.info("Ticket %s unblocked → READY", t.id)

        return unlocked

    @staticmethod
    def _gather_dependency_outputs(
        ticket: Ticket, store: dict[str, Ticket]
    ) -> dict[str, str]:
        """Collect output_summary values from completed dependencies."""
        outputs: dict[str, str] = {}
        for dep_id in ticket.depends_on:
            dep = store.get(dep_id)
            if dep and dep.output_summary:
                outputs[dep_id] = dep.output_summary
        return outputs

    async def _load_session_tickets(self, session_id: str) -> None:
        """Load tickets from the database into the in-memory cache if
        they haven't been loaded yet for this session."""
        if session_id in self._tickets:
            return

        tickets = await self.db.get_tickets_by_session(session_id)
        self._tickets[session_id] = {t.id: t for t in tickets}
        logger.debug(
            "Loaded %d tickets for session %s from DB",
            len(tickets),
            session_id,
        )
