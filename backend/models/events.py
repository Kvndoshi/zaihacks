"""WebSocket event types for real-time communication."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    SESSION_CREATED = "session_created"
    SESSION_MESSAGE = "session_message"
    DELIBERATION_COMPLETE = "deliberation_complete"
    TICKETS_GENERATED = "tickets_generated"
    TICKET_CLAIMED = "ticket_claimed"
    TICKET_COMPLETED = "ticket_completed"
    TICKET_FAILED = "ticket_failed"
    WORKFLOW_UPDATE = "workflow_update"
    TICKETS_REFINED = "tickets_refined"
    TICKET_DELETED = "ticket_deleted"
    TICKET_MODIFIED = "ticket_modified"
    AGENT_CONNECTED = "agent_connected"
    AGENT_DISCONNECTED = "agent_disconnected"
    STATUS_UPDATE = "status_update"
    ISSUES_FETCHED = "issues_fetched"
    ISSUE_TICKETS_GENERATED = "issue_tickets_generated"
    ISSUE_GROUP_TOGGLED = "issue_group_toggled"


class WSEvent(BaseModel):
    type: EventType
    data: dict = Field(default_factory=dict)
    session_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
