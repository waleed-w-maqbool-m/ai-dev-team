"""Message envelope every agent invocation appends to the shared audit trail."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    plan = "plan"
    implementation = "implementation"
    test_report = "test_report"
    review = "review"
    clarification_request = "clarification_request"
    documentation = "documentation"
    status = "status"


class AgentMessage(BaseModel):
    sender: str
    recipient: str = "state"
    message_type: MessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
