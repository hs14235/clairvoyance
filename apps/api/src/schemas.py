"""Request/response models for the chat API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Sentiment(str, Enum):
    calm = "calm"
    neutral = "neutral"
    sad = "sad"
    anxious = "anxious"
    angry = "angry"
    distressed = "distressed"


class SessionStatus(str, Enum):
    ai = "ai"  # AI is replying, nothing flagged
    flagged = "flagged"  # triage asked for a human, AI still replying
    counselor = "counselor"  # a counselor took over, AI is paused


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)


class ChatMessageResponse(BaseModel):
    text_response: str
    sentiment: Sentiment
    intensity: int = Field(ge=1, le=10)
    animation_trigger: str
    human_takeover_flag: bool
    session_id: str
    # True once a counselor has taken over: text_response is a holding line, not AI output.
    ai_paused: bool = False


class MessageOut(BaseModel):
    role: str
    text: str
    at: datetime
    sentiment: Sentiment | None = None
    intensity: int | None = None


class SessionSummary(BaseModel):
    id: str
    status: SessionStatus
    sentiment: Sentiment
    intensity: int
    peak_intensity: int
    message_count: int
    last_client_message: str | None
    created_at: datetime
    updated_at: datetime
    flagged_at: datetime | None
    taken_over_at: datetime | None


class SessionDetail(SessionSummary):
    messages: list[MessageOut]


class TranscriptionResponse(BaseModel):
    text: str
