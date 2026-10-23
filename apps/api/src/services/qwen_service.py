"""Model layer: an interface the rest of the app depends on, plus implementations.

Only `StubQwenClient` exists today. When Qwen API access is available, add a
`QwenClient` that implements `LLMClient` and select it in `get_llm_client`.
"""

import os
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelAnalysis:
    """Raw model output. Not trusted: triage rules validate it downstream."""

    text_response: str
    sentiment: str
    intensity: int
    animation_trigger: str


class LLMClient(Protocol):
    async def analyze(self, message: str) -> ModelAnalysis: ...


# (keywords, sentiment, intensity, animation_trigger), checked in order.
_STUB_RULES: list[tuple[tuple[str, ...], str, int, str]] = [
    (("hopeless", "can't go on", "cant go on", "worthless", "no way out"), "distressed", 9, "concerned_lean_in"),
    (("panic", "can't breathe", "cant breathe", "overwhelmed"), "anxious", 7, "supportive_nod"),
    (("anxious", "worried", "nervous", "stressed"), "anxious", 4, "supportive_nod"),
    (("angry", "furious", "hate"), "angry", 5, "steady_gaze"),
    (("sad", "lonely", "down", "crying"), "sad", 4, "soft_smile"),
    (("good", "better", "calm", "happy"), "calm", 2, "gentle_smile"),
]

_STUB_REPLIES = {
    "distressed": "I'm really glad you told me. You don't have to carry this alone, and I'd like to bring in someone who can support you right now.",
    "anxious": "I hear how overwhelming that feels. Let's ground ourselves together with a slow breath.",
    "angry": "It sounds like something really got to you. I'm listening.",
    "sad": "That sounds heavy. Do you want to tell me more about what's been going on?",
    "calm": "I'm glad to hear that. What's been helping?",
    "neutral": "Thanks for sharing. How has your week been overall?",
}


class StubQwenClient:
    """Deterministic keyword-based stand-in for Qwen, for dev and tests."""

    async def analyze(self, message: str) -> ModelAnalysis:
        text = message.lower()
        for keywords, sentiment, intensity, trigger in _STUB_RULES:
            if any(k in text for k in keywords):
                return ModelAnalysis(_STUB_REPLIES[sentiment], sentiment, intensity, trigger)
        return ModelAnalysis(_STUB_REPLIES["neutral"], "neutral", 1, "idle_listen")


def get_llm_client() -> LLMClient:
    """FastAPI dependency. Tests replace it via `app.dependency_overrides`."""
    provider = os.getenv("LLM_PROVIDER", "stub")
    if provider == "stub":
        return StubQwenClient()
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider!r}")
