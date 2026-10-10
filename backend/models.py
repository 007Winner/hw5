"""Structured types shared by the Campus Customs agent team."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentRole(StrEnum):
    BOSS = "boss"
    INVENTORY = "inventory"
    ACCOUNTING = "accounting"
    FACILITIES = "facilities"
    CUSTOMER_SERVICE = "customer_service"


class AgentDecision(BaseModel):
    """A bounded, auditable result returned by every specialist."""

    role: AgentRole
    ticket_id: int | None = None
    summary: str
    recommended_action: str
    facts: list[str] = Field(default_factory=list)
    delegated_to: list[AgentRole] = Field(default_factory=list)
    requires_human_approval: bool = False
    external_message_draft: str | None = None
    stop_reason: str = "completed"


class AuditRecord(BaseModel):
    timestamp: str
    event: str
    agent: AgentRole | None = None
    tool_name: str | None = None
    ticket_id: int | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    stop_reason: str | None = None


class TeamRunResult(BaseModel):
    """Top-level result used by a future FastAPI route or dashboard."""

    decision: AgentDecision
    steps_used: int
    max_steps: int
    max_depth: int
