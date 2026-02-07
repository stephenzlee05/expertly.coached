from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RecordKind(str, Enum):
    summary = "summary"
    transcript = "transcript"
    data = "data"


# ---------------------------------------------------------------------------
# Core document model (mirrors the MongoDB document shape)
# ---------------------------------------------------------------------------

class AgentMemoryRecord(BaseModel):
    agentId: str
    personKeyType: str = "phone"
    personKey: str
    personName: str | None = None
    personId: str | None = None
    topicId: str
    topicName: str
    coachingTemplateCode: str | None = None
    recordKind: RecordKind
    conversationId: str | None = None
    sequence: int | None = None
    text: str | None = None
    data: dict[str, Any] | None = None
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConversationSession(BaseModel):
    conversationId: str
    agentId: str
    personKeyType: str = "phone"
    personKey: str
    topicId: str
    topicName: str
    coachingTemplateCode: str | None = None
    mode: str = "accountability"
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# API schemas – lookupPersonAndTopics
# ---------------------------------------------------------------------------

class TopicInfo(BaseModel):
    topicId: str
    topicName: str
    lastSummarySnippet: str | None = None
    lastUpdatedAt: datetime | None = None


class LookupPersonResponse(BaseModel):
    success: bool = True
    personName: str | None = None
    personId: str | None = None
    topics: list[TopicInfo] = []


# ---------------------------------------------------------------------------
# API schemas – startTopicSession
# ---------------------------------------------------------------------------

class StartTopicSessionResponse(BaseModel):
    success: bool = True
    topicId: str
    topicName: str
    conversationId: str
    mode: str
    coachingTemplateCode: str | None = None
    summarySoFar: str = ""
    personId: str | None = None


# ---------------------------------------------------------------------------
# API schemas – saveConversation
# ---------------------------------------------------------------------------

class SaveConversationResponse(BaseModel):
    success: bool = True
    savedTranscriptRecordId: str | None = None
    savedSummaryRecordId: str | None = None
    error: str | None = None
