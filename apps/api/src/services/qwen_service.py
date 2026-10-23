"""Model layer: an interface the rest of the app depends on, plus implementations.

- `StubQwenClient`: deterministic keyword stand-in. Default, used by tests and CI.
- `OpenAICompatQwenClient`: any OpenAI-compatible `/chat/completions` server
  serving Qwen, e.g. a local Ollama (`qwen2.5:3b`) or a hosted Qwen API.

Select with `LLM_PROVIDER` (`stub` | `openai`), see `get_llm_client`.
"""

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)


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


SYSTEM_PROMPT = """You are Clairvoyance, a warm, calm intake companion for a \
university counseling service. You are not a therapist and never diagnose. \
Reply in 1-3 short sentences: reflect what the person said, then ask one gentle \
open question or offer one grounding step.

Respond with ONLY a JSON object, no markdown, with exactly these keys:
{"text_response": string,
 "sentiment": one of "calm","neutral","sad","anxious","angry","distressed",
 "intensity": integer 1-10 (1 = settled, 10 = acute crisis),
 "animation_trigger": one of "idle_listen","supportive_nod","soft_smile",
   "gentle_smile","steady_gaze","concerned_lean_in"}"""

# Reply used when the model is unreachable or returns unusable output. Triage
# rules still run on the user's message, so crisis keywords still escalate.
FALLBACK_ANALYSIS = ModelAnalysis(
    "I'm here and listening. Could you tell me a bit more about that?",
    "neutral",
    1,
    "idle_listen",
)


def parse_model_json(content: str) -> ModelAnalysis:
    """Parse the model's JSON reply. Raises ValueError on anything unusable.

    Small local models sometimes wrap JSON in ```fences``` or add prose, so we
    take the outermost {...} block.
    """
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    data = json.loads(content[start : end + 1])
    text = str(data.get("text_response", "")).strip()
    if not text:
        raise ValueError("empty text_response")
    try:
        intensity = int(data.get("intensity", 1))
    except (TypeError, ValueError):
        intensity = 1
    return ModelAnalysis(
        text_response=text,
        sentiment=str(data.get("sentiment", "neutral")),
        intensity=intensity,
        animation_trigger=str(data.get("animation_trigger", "idle_listen")),
    )


class OpenAICompatQwenClient:
    """Qwen over any OpenAI-compatible chat completions API (Ollama, DashScope, vLLM)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._transport = transport  # tests inject httpx.MockTransport

    async def analyze(self, message: str) -> ModelAnalysis:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message},
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self._transport) as client:
                res = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                res.raise_for_status()
                content = res.json()["choices"][0]["message"]["content"]
            return parse_model_json(content)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            # Never fail the chat request because the model misbehaved.
            logger.warning("LLM call failed, using fallback reply: %s", exc)
            return FALLBACK_ANALYSIS


@lru_cache
def _openai_client_from_env() -> OpenAICompatQwenClient:
    return OpenAICompatQwenClient(
        base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
        model=os.getenv("LLM_MODEL", "qwen2.5:3b"),
        api_key=os.getenv("LLM_API_KEY") or None,
        timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
    )


def get_llm_client() -> LLMClient:
    """FastAPI dependency. Tests replace it via `app.dependency_overrides`."""
    provider = os.getenv("LLM_PROVIDER", "stub")
    if provider == "stub":
        return StubQwenClient()
    if provider == "openai":
        return _openai_client_from_env()
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider!r}")
