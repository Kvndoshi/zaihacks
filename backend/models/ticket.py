"""Ticket models for the work-breakdown / orchestration layer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TicketStatus(str, Enum):
    BLOCKED = "blocked"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TicketPriority(int, Enum):
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class TicketDomain(str, Enum):
    BACKEND = "backend"
    FRONTEND = "frontend"
    DATABASE = "database"
    AUTH = "auth"
    API = "api"
    TESTING = "testing"
    INFRA = "infra"
    DOCS = "docs"
    MARKETING = "marketing"
    DESIGN = "design"
    RESEARCH = "research"
    OPERATIONS = "operations"
    CONTENT = "content"
    LEGAL = "legal"
    BUSINESS = "business"
    GENERAL = "general"


def _next_ticket_id() -> str:
    """Generate a FRIC-XXX style ticket id using a short uuid suffix."""
    short = uuid.uuid4().hex[:6].upper()
    return f"FRIC-{short}"


class Ticket(BaseModel):
    id: str = Field(default_factory=_next_ticket_id)
    session_id: str
    title: str
    description: str = Field(
        ..., description="FULL self-contained description of the work item"
    )
    layer: int = Field(..., ge=0, le=4, description="Execution layer (0-4)")
    domain: TicketDomain
    priority: TicketPriority = TicketPriority.MEDIUM
    status: TicketStatus = TicketStatus.BLOCKED
    depends_on: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    files_to_create: list[str] = Field(default_factory=list)
    files_to_modify: list[str] = Field(default_factory=list)
    output_summary: Optional[str] = None
    agent_id: Optional[str] = None
    source_issue_id: Optional[str] = None
    source_issue_title: Optional[str] = None
    active: bool = True
    claimed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
