"""Generate implementation tickets from selected GitHub issues via LLM."""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.models.codebase import CodebaseAnalysis, GitHubIssue
from backend.models.ticket import Ticket, TicketDomain, TicketPriority, TicketStatus

logger = logging.getLogger(__name__)

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
    "infra": TicketDomain.INFRA,
    "infrastructure": TicketDomain.INFRA,
    "devops": TicketDomain.INFRA,
    "docs": TicketDomain.DOCS,
    "documentation": TicketDomain.DOCS,
}

_PRIORITY_MAP: dict[str, TicketPriority] = {
    "critical": TicketPriority.CRITICAL,
    "high": TicketPriority.HIGH,
    "medium": TicketPriority.MEDIUM,
    "low": TicketPriority.LOW,
}

_SYSTEM_PROMPT = """\
You are a senior software architect generating implementation tickets from GitHub issues.

RULES:
1. For EACH issue, generate 1-5 implementation tickets.
2. Each ticket must be SELF-CONTAINED with full context. Never reference other tickets.
3. Assign layers (0-4): 0=foundational, 1=core, 2=business logic, 3=integration, 4=polish.
4. Use temp_id values "T1", "T2", ... across ALL tickets (sequential).
5. depends_on may reference temp_ids from other issues if there is a real dependency.
6. Include 2-5 acceptance criteria per ticket.
7. Assign domain: backend, frontend, database, auth, api, testing, infra, docs.
8. Assign priority: critical, high, medium, low.

Respond with JSON:
{
  "issue_tickets": [
    {
      "source_issue_github_id": 42,
      "tickets": [
        {
          "temp_id": "T1",
          "title": "...",
          "description": "Full self-contained description...",
          "layer": 0,
          "domain": "backend",
          "priority": "high",
          "depends_on": [],
          "acceptance_criteria": ["..."],
          "files_to_create": [],
          "files_to_modify": []
        }
      ]
    }
  ]
}
"""


class IssueTicketGenerator:
    """Generate implementation tickets from GitHub issues using LLM."""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def generate_from_issues(
        self,
        issues: list[GitHubIssue],
        codebase: Optional[CodebaseAnalysis],
        session_id: str,
    ) -> list[Ticket]:
        prompt = self._build_prompt(issues, codebase)

        raw = await self.llm.structured_output(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.4,
        )

        issue_tickets = raw.get("issue_tickets", [])
        if not issue_tickets:
            logger.warning("LLM returned zero issue tickets")
            return []

        # Build issue id lookup: github_id -> GitHubIssue
        issue_map = {iss.github_id: iss for iss in issues}

        tickets = self._parse_tickets(issue_tickets, issue_map, session_id)
        self._assign_layers(tickets)
        self._set_initial_statuses(tickets)
        return tickets

    def _build_prompt(
        self,
        issues: list[GitHubIssue],
        codebase: Optional[CodebaseAnalysis],
    ) -> str:
        parts: list[str] = []

        if codebase:
            parts.append(f"## Codebase Context\n{codebase.summary}")
            if codebase.tech_stack.frameworks:
                parts.append(f"Frameworks: {', '.join(codebase.tech_stack.frameworks)}")

        parts.append("## GitHub Issues to implement\n")
        for iss in issues:
            labels_str = ", ".join(lbl.name for lbl in iss.labels) if iss.labels else "none"
            body_preview = (iss.body[:500] + "...") if len(iss.body) > 500 else iss.body
            parts.append(
                f"### Issue #{iss.github_id}: {iss.title}\n"
                f"Type: {iss.issue_type.value} | Labels: {labels_str}\n"
                f"{body_preview}\n"
            )

        parts.append(
            "Generate implementation tickets for these issues. "
            "Make every ticket self-contained with full context."
        )
        return "\n\n".join(parts)

    def _parse_tickets(
        self,
        issue_tickets: list[dict[str, Any]],
        issue_map: dict[int, GitHubIssue],
        session_id: str,
    ) -> list[Ticket]:
        # Collect all raw tickets with their source issue info
        all_raw: list[tuple[dict[str, Any], int]] = []
        for group in issue_tickets:
            src_id = group.get("source_issue_github_id", 0)
            for rt in group.get("tickets", []):
                all_raw.append((rt, src_id))

        # Build temp_id -> FRIC-XXX mapping
        temp_to_fric: dict[str, str] = {}
        for idx, (rt, _) in enumerate(all_raw, start=1):
            temp_id = rt.get("temp_id", f"T{idx}")
            fric_id = f"FRIC-{idx:03d}"
            temp_to_fric[temp_id] = fric_id

        tickets: list[Ticket] = []
        for idx, (rt, src_github_id) in enumerate(all_raw, start=1):
            temp_id = rt.get("temp_id", f"T{idx}")
            fric_id = temp_to_fric[temp_id]

            raw_deps = rt.get("depends_on", [])
            resolved_deps = [temp_to_fric[d] for d in raw_deps if d in temp_to_fric]

            raw_domain = str(rt.get("domain", "backend")).lower().strip()
            domain = _DOMAIN_MAP.get(raw_domain, TicketDomain.BACKEND)

            raw_priority = str(rt.get("priority", "medium")).lower().strip()
            priority = _PRIORITY_MAP.get(raw_priority, TicketPriority.MEDIUM)

            layer = max(0, min(4, int(rt.get("layer", 0))))

            source_issue = issue_map.get(src_github_id)
            source_issue_id = source_issue.id if source_issue else None
            source_issue_title = f"#{src_github_id}: {source_issue.title}" if source_issue else None

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
                source_issue_id=source_issue_id,
                source_issue_title=source_issue_title,
            )
            tickets.append(ticket)

        # Populate blocks (inverse of depends_on)
        ticket_map = {t.id: t for t in tickets}
        for t in tickets:
            for dep_id in t.depends_on:
                if dep_id in ticket_map and t.id not in ticket_map[dep_id].blocks:
                    ticket_map[dep_id].blocks.append(t.id)

        return tickets

    @staticmethod
    def _assign_layers(tickets: list[Ticket]) -> None:
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
            layer = min(layer, 4)
            computed[tid] = layer
            return layer

        for t in tickets:
            t.layer = _compute(t.id)

    @staticmethod
    def _set_initial_statuses(tickets: list[Ticket]) -> None:
        for t in tickets:
            t.status = TicketStatus.READY if not t.depends_on else TicketStatus.BLOCKED
