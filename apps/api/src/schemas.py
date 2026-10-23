"""Request/response models for the chat API."""

from enum import Enum

from pydantic import BaseModel, Field


class Sentiment(str, Enum):
    calm = "calm"
    neutral = "neutral"
    sad = "sad"
    anxious = "anxious"
    angry = "angry"
    distressed = "distressed"


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class ChatMessageResponse(BaseModel):
    text_response: str
    sentiment: Sentiment
    intensity: int = Field(ge=1, le=10)
    animation_trigger: str
    human_takeover_flag: bool


class TranscriptionResponse(BaseModel):
    text: str
