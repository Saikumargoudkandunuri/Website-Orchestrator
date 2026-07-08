"""Typed inter-agent message models (M6 Build Phase F)."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from agentic.agents.types import JsonObject


class MessageType(str, Enum):
    REQUEST = "request"
    RESPONSE = "response"
    PROPOSAL = "proposal"
    QUESTION = "question"
    EVIDENCE = "evidence"
    COMPLETION = "completion"
    FAILURE = "failure"
    HEARTBEAT = "heartbeat"


class AgentMessage(BaseModel):
    """Immutable, strongly typed message exchanged between agents."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    mission_id: str
    tenant_id: str
    sender: str
    recipient: str
    message_type: MessageType
    body: JsonObject = Field(default_factory=dict)
    trace_id: str
    correlation_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RequestMessage(AgentMessage):
    message_type: MessageType = MessageType.REQUEST


class ResponseMessage(AgentMessage):
    message_type: MessageType = MessageType.RESPONSE


class ProposalMessage(AgentMessage):
    message_type: MessageType = MessageType.PROPOSAL


class QuestionMessage(AgentMessage):
    message_type: MessageType = MessageType.QUESTION


class EvidenceMessage(AgentMessage):
    message_type: MessageType = MessageType.EVIDENCE


class CompletionMessage(AgentMessage):
    message_type: MessageType = MessageType.COMPLETION


class FailureMessage(AgentMessage):
    message_type: MessageType = MessageType.FAILURE


class HeartbeatMessage(AgentMessage):
    message_type: MessageType = MessageType.HEARTBEAT
