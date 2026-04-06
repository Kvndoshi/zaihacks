"""Workflow graph models — used by the frontend to render the DAG visualisation."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from backend.models.ticket import TicketDomain, TicketStatus


class WorkflowNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ticket_id: str
    label: str
    layer: int
    domain: TicketDomain
    status: TicketStatus
    position_x: float = 0.0
    position_y: float = 0.0


class WorkflowEdge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    target: str
    animated: bool = False


class WorkflowGraph(BaseModel):
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
