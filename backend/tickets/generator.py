"""Ticket generation from deliberation results using LLM structured output."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from backend.models.codebase import CodebaseAnalysis
from backend.models.session import DeliberationSession
from backend.models.ticket import Ticket, TicketDomain, TicketPriority, TicketStatus

logger = logging.getLogger(__name__)

# Maps raw LLM domain strings to our enum
_DOMAIN_MAP: dict[str, TicketDomain] = {
    "backend": TicketDomain.BACKEND,
    "frontend": TicketDomain.FRONTEND,
    "database": TicketDomain.DATABASE,
    "db": TicketDomain.DATABASE,
    "auth": TicketDomain.AUTH,
    "authentication": TicketDomain.AUTH,
    "api": TicketDomain.API,
    "testing": TicketDomain.TESTING,
    "test": TicketDomain.TESTING,
    "tests": TicketDomain.TESTING,
    "infra": TicketDomain.INFRA,
    "infrastructure": TicketDomain.INFRA,
    "devops": TicketDomain.INFRA,
    "docs": TicketDomain.DOCS,
    "documentation": TicketDomain.DOCS,
    "marketing": TicketDomain.MARKETING,
    "design": TicketDomain.DESIGN,
    "ux": TicketDomain.DESIGN,
    "ui": TicketDomain.DESIGN,
    "research": TicketDomain.RESEARCH,
    "operations": TicketDomain.OPERATIONS,
    "ops": TicketDomain.OPERATIONS,
    "content": TicketDomain.CONTENT,
    "copywriting": TicketDomain.CONTENT,
    "legal": TicketDomain.LEGAL,
    "compliance": TicketDomain.LEGAL,
    "business": TicketDomain.BUSINESS,
    "strategy": TicketDomain.BUSINESS,
    "general": TicketDomain.GENERAL,
}

_PRIORITY_MAP: dict[str, TicketPriority] = {
    "critical": TicketPriority.CRITICAL,
    "high": TicketPriority.HIGH,
    "medium": TicketPriority.MEDIUM,
    "low": TicketPriority.LOW,
}

_GENERATION_SYSTEM_PROMPT = """\
You are a senior project planner generating implementation tickets for a project.
Projects can be ANY type of work — software development, marketing campaigns, design \
projects, research initiatives, business operations, content creation, legal reviews, \
hiring plans, or anything else. Adapt your tickets to the nature of the work.

RULES:
1. Generate between 5 and 12 tickets organized into layers (0-4).
   IMPORTANT: Batch related small tasks into single tickets. For example, do NOT create
   separate tickets for individual functions like addition, subtraction, multiplication —
   combine them into one ticket like 'Implement core arithmetic operations'. Each ticket
   should represent a meaningful, independently completable unit of work, not a single task.
   - Layer 0: foundational work with NO dependencies (research, setup, planning, schemas)
   - Layer 1: depends only on layer-0 tickets (core work, data models, initial drafts)
   - Layer 2: depends on layer-0 and/or layer-1 (integration, execution, business logic)
   - Layer 3: depends on lower layers (review, testing, refinement)
   - Layer 4: depends on lower layers (polish, launch, documentation)
2. Each ticket MUST be SELF-CONTAINED. Include FULL context in the description.
   Never say "as discussed above", "see ticket X", or "the above".
   A person reading ONLY that ticket must know exactly what to do.
3. Include 2-5 concrete, testable acceptance criteria per ticket.
4. For software/code tickets, list specific files_to_create and files_to_modify.
   For non-technical tickets (marketing, design, research, etc.), these can be empty arrays.
5. Assign a domain from: backend, frontend, database, auth, api, testing, infra, docs, \
marketing, design, research, operations, content, legal, business, general.
   Pick the domain that best matches the work — use "general" if nothing else fits.
6. Assign a priority: critical (blockers), high (core), medium (features), low (polish).
7. Use temp_id values like "T1", "T2", ... for dependency references.
   depends_on should reference other temp_ids from this same list.
8. If codebase analysis is provided, reference ACTUAL file paths from it.
9. If risks were identified, create tickets that mitigate them.

Respond with a JSON object:
{
  "tickets": [
    {
      "temp_id": "T1",
      "title": "...",
      "description": "Full self-contained description...",
      "layer": 0,
      "domain": "backend",
      "priority": "critical",
      "depends_on": [],
      "acceptance_criteria": ["Criterion 1", "Criterion 2"],
      "files_to_create": ["path/to/file.py"],
      "files_to_modify": []
    }
  ]
}
"""


class TicketGenerator:
    """Generates layered, self-contained tickets from a deliberation session."""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def generate(
        self,
        session: DeliberationSession,
        codebase: Optional[CodebaseAnalysis] = None,
    ) -> list[Ticket]:
        """Generate layered, self-contained tickets from deliberation results.

        Args:
            session: The completed deliberation session with refined_idea,
                     key_insights, and risks.
            codebase: Optional codebase analysis to ground tickets in real files.

        Returns:
            A list of Ticket models with sequential FRIC-XXX IDs,
            validated dependency graph, and correct initial statuses.
        """
        prompt = self._build_prompt(session, codebase)
        raw = await self.llm.structured_output(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=_GENERATION_SYSTEM_PROMPT,
            temperature=0.4,
        )

        raw_tickets = raw.get("tickets", [])
        if not raw_tickets:
            logger.warning("LLM returned zero tickets; retrying once")
            raw = await self.llm.structured_output(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=_GENERATION_SYSTEM_PROMPT,
                temperature=0.5,
            )
            raw_tickets = raw.get("tickets", [])

        tickets = self._parse_tickets(raw_tickets, session.id)
        self._assign_layers(tickets)
        self._set_initial_statuses(tickets)
        return tickets

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        session: DeliberationSession,
        codebase: Optional[CodebaseAnalysis],
    ) -> str:
        parts: list[str] = []

        # Core idea
        idea = session.refined_idea or session.idea
        parts.append(f"## Project Idea\n{idea}")

        # Key insights from deliberation
        if session.key_insights:
            insights = "\n".join(f"- {i}" for i in session.key_insights)
            parts.append(f"## Key Insights from Deliberation\n{insights}")

        # Identified risks
        if session.risks:
            risks = "\n".join(f"- {r}" for r in session.risks)
            parts.append(f"## Identified Risks\n{risks}")

        # Codebase context
        if codebase:
            parts.append(self._codebase_section(codebase))

        parts.append(
            "Generate implementation tickets following the rules. "
            "Make sure every ticket is self-contained with full context."
        )
        return "\n\n".join(parts)

    @staticmethod
    def _codebase_section(codebase: CodebaseAnalysis) -> str:
        lines = ["## Existing Codebase"]
        if codebase.summary:
            lines.append(codebase.summary)

        ts = codebase.tech_stack
        if ts.languages:
            lang_str = ", ".join(
                f"{lang} ({count} files)" for lang, count in ts.languages.items()
            )
            lines.append(f"**Languages:** {lang_str}")
        if ts.frameworks:
            lines.append(f"**Frameworks:** {', '.join(ts.frameworks)}")
        if ts.databases:
            lines.append(f"**Databases:** {', '.join(ts.databases)}")

        if codebase.key_files:
            key_paths = [f.path for f in codebase.key_files[:20]]
            lines.append("**Key files:**\n" + "\n".join(f"- `{p}`" for p in key_paths))

        if codebase.architecture_patterns:
            patterns = [
                f"- {p.name}: {p.description}"
                for p in codebase.architecture_patterns
            ]
            lines.append("**Architecture patterns:**\n" + "\n".join(patterns))

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Parsing & validation
    # ------------------------------------------------------------------

    def _parse_tickets(
        self, raw_tickets: list[dict[str, Any]], session_id: str
    ) -> list[Ticket]:
        """Parse raw LLM JSON dicts into Ticket models with sequential IDs."""

        # Build temp_id -> FRIC-XXX mapping
        temp_to_fric: dict[str, str] = {}
        for idx, rt in enumerate(raw_tickets, start=1):
            temp_id = rt.get("temp_id", f"T{idx}")
            fric_id = f"FRIC-{idx:03d}"
            temp_to_fric[temp_id] = fric_id

        tickets: list[Ticket] = []
        for idx, rt in enumerate(raw_tickets, start=1):
            temp_id = rt.get("temp_id", f"T{idx}")
            fric_id = temp_to_fric[temp_id]

            # Resolve dependency temp_ids to FRIC IDs
            raw_deps = rt.get("depends_on", [])
            resolved_deps = [
                temp_to_fric[d]
                for d in raw_deps
                if d in temp_to_fric
            ]

            # Parse domain
            raw_domain = str(rt.get("domain", "backend")).lower().strip()
            domain = _DOMAIN_MAP.get(raw_domain, TicketDomain.BACKEND)

            # Parse priority
            raw_priority = str(rt.get("priority", "medium")).lower().strip()
            priority = _PRIORITY_MAP.get(raw_priority, TicketPriority.MEDIUM)

            # Parse layer (clamp to 0-4)
            layer = max(0, min(4, int(rt.get("layer", 0))))

            ticket = Ticket(
                id=fric_id,
                session_id=session_id,
                title=rt.get("title", f"Ticket {idx}"),
                description=rt.get("description", ""),
                layer=layer,
                domain=domain,
                priority=priority,
                depends_on=resolved_deps,
                acceptance_criteria=rt.get("acceptance_criteria", []),
                files_to_create=rt.get("files_to_create", []),
                files_to_modify=rt.get("files_to_modify", []),
            )
            tickets.append(ticket)

        # Populate the `blocks` field (inverse of depends_on)
        ticket_map = {t.id: t for t in tickets}
        for t in tickets:
            for dep_id in t.depends_on:
                if dep_id in ticket_map:
                    if t.id not in ticket_map[dep_id].blocks:
                        ticket_map[dep_id].blocks.append(t.id)

        return tickets

    @staticmethod
    def _assign_layers(tickets: list[Ticket]) -> None:
        """Re-compute layers from the dependency graph to ensure correctness.

        Layer = 0 if no dependencies; otherwise max(dep layers) + 1.
        """
        ticket_map = {t.id: t for t in tickets}
        computed: dict[str, int] = {}

        def _compute(tid: str) -> int:
            if tid in computed:
                return computed[tid]
            t = ticket_map.get(tid)
            if t is None:
                return 0
            if not t.depends_on:
                computed[tid] = 0
                return 0
            dep_layers = [_compute(d) for d in t.depends_on if d in ticket_map]
            layer = (max(dep_layers) + 1) if dep_layers else 0
            layer = min(layer, 4)  # clamp
            computed[tid] = layer
            return layer

        for t in tickets:
            t.layer = _compute(t.id)

    @staticmethod
    def _set_initial_statuses(tickets: list[Ticket]) -> None:
        """Tickets with no dependencies start READY; others start BLOCKED."""
        for t in tickets:
            if not t.depends_on:
                t.status = TicketStatus.READY
            else:
                t.status = TicketStatus.BLOCKED
