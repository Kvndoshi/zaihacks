"""Session and message models for the deliberation engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    DELIBERATING = "deliberating"
    GENERATING_TICKETS = "generating_tickets"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class MessageRole(str, Enum):
    USER = "user"
    FRICTION = "friction"
    SYSTEM = "system"


class SessionMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence_score: Optional[float] = None
    phase: Optional[str] = None
    web_searched: bool = False


class DeliberationSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    idea: str
    status: SessionStatus = SessionStatus.DELIBERATING
    messages: list[SessionMessage] = Field(default_factory=list)
    key_insights: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    refined_idea: Optional[str] = None
    codebase_id: Optional[str] = None
    agent_prompt: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
