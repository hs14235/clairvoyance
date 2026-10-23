"""Model layer: an interface the rest of the app depends on, plus implementations.

- `StubQwenClient`: deterministic keyword stand-in. Default, used by tests and CI.
- `OpenAICompatQwenClient`: any OpenAI-compatible `/chat/completions` server
  serving Qwen, e.g. a local Ollama (`qwen2.5:1.5b` / `qwen2.5:7b`) or a hosted
  Qwen API.

Select with `LLM_PROVIDER` (`stub` | `openai`), see `get_llm_client`.
"""

import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, Protocol

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelAnalysis:
    """Raw model output. Not trusted: triage rules validate it downstream."""

    text_response: str
    sentiment: str
    intensity: int
    animation_trigger: str
    # Set when the model could not be used and this is a canned reply.
    fallback_reason: str | None = None


@dataclass(frozen=True)
class Turn:
    """One earlier message in the conversation, oldest first."""

    role: Literal["user", "assistant"]
    text: str


class LLMClient(Protocol):
    async def analyze(self, message: str, history: Sequence[Turn] = ()) -> ModelAnalysis: ...


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

    async def analyze(self, message: str, history: Sequence[Turn] = ()) -> ModelAnalysis:
        text = message.lower()
        for keywords, sentiment, intensity, trigger in _STUB_RULES:
            if any(k in text for k in keywords):
                return ModelAnalysis(_STUB_REPLIES[sentiment], sentiment, intensity, trigger)
        return ModelAnalysis(_STUB_REPLIES["neutral"], "neutral", 1, "idle_listen")


SENTIMENTS = ("calm", "neutral", "sad", "anxious", "angry", "distressed")
ANIMATION_TRIGGERS = (
    "idle_listen",
    "supportive_nod",
    "soft_smile",
    "gentle_smile",
    "steady_gaze",
    "concerned_lean_in",
)

SYSTEM_PROMPT = f"""You are Clairvoyance, the intake companion for a university \
counseling service. You speak with students before a student counselor joins.

How to reply (text_response):
- Warm, plain, calm. 1-3 short sentences, under 60 words: it is read aloud.
- Reflect what the person said in your own words, then ask ONE gentle open \
question or offer ONE small grounding step (e.g. a slow breath).
- You are not a therapist: never diagnose, never give medication advice, never \
promise confidentiality, never claim to be human.
- If they mention self-harm, suicide or being unsafe: respond with care, say a \
counselor is being brought in now, and encourage them to stay with you.

How to rate the person's CURRENT message (not your reply):
- sentiment: one of {", ".join(SENTIMENTS)}.
- intensity 1-10: 1-2 settled; 3-4 everyday stress; 5-6 struggling, affecting \
sleep/study/relationships; 7 overwhelmed, panic; 8-9 hopeless, unsafe, \
self-harm thoughts; 10 immediate danger.
- animation_trigger (avatar gesture): one of {", ".join(ANIMATION_TRIGGERS)}. \
Use concerned_lean_in for distress, supportive_nod for worry, soft_smile for \
sadness, gentle_smile for good news, steady_gaze for anger, idle_listen otherwise.

Output ONLY a JSON object with keys text_response, sentiment, intensity, \
animation_trigger. No markdown, no extra keys.

Example input: "my exams are next week and I can't sleep"
Example output: {{"text_response": "Exams plus no sleep is a hard mix. What's \
keeping your mind busy when you lie down?", "sentiment": "anxious", \
"intensity": 5, "animation_trigger": "supportive_nod"}}"""

# JSON Schema for structured output. Ollama turns this into a grammar, so even
# small models can only emit valid keys and enum values.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "text_response": {"type": "string"},
        "sentiment": {"type": "string", "enum": list(SENTIMENTS)},
        "intensity": {"type": "integer", "minimum": 1, "maximum": 10},
        "animation_trigger": {"type": "string", "enum": list(ANIMATION_TRIGGERS)},
    },
    "required": ["text_response", "sentiment", "intensity", "animation_trigger"],
    "additionalProperties": False,
}

# Labels small models produce instead of ours.
_SENTIMENT_ALIASES = {
    "anxiety": "anxious", "worried": "anxious", "stressed": "anxious", "nervous": "anxious",
    "fearful": "anxious", "scared": "anxious", "sadness": "sad", "depressed": "sad",
    "lonely": "sad", "upset": "sad", "anger": "angry", "frustrated": "angry",
    "happy": "calm", "positive": "calm", "content": "calm", "hopeful": "calm",
    "crisis": "distressed", "hopeless": "distressed", "desperate": "distressed",
}

# Reply used when the model is unreachable or returns unusable output. Triage
# rules still run on the user's text, so crisis keywords still escalate.
FALLBACK_ANALYSIS = ModelAnalysis(
    "I'm here and listening. Could you tell me a bit more about that?",
    "neutral",
    1,
    "idle_listen",
)

# How many earlier messages to send the model. Keeps prompts short on CPU.
HISTORY_TURNS = 8


class LLMUnavailable(Exception):
    """The model server can't be used at all. `str()` says how to fix it."""


def parse_model_json(content: str) -> ModelAnalysis:
    """Parse the model's JSON reply. Raises ValueError on anything unusable.

    Small local models sometimes wrap JSON in ```fences``` or add prose, so we
    take the outermost {...} block.
    """
    start, end = content.find("{"), content.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    data = json.loads(content[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("model output is not a JSON object")
    text = str(data.get("text_response", "")).strip()
    if not text:
        raise ValueError("empty text_response")
    try:
        intensity = int(data.get("intensity", 1))
    except (TypeError, ValueError):
        intensity = 1
    sentiment = str(data.get("sentiment", "neutral")).strip().lower()
    trigger = str(data.get("animation_trigger", "idle_listen")).strip().lower()
    return ModelAnalysis(
        text_response=text,
        sentiment=_SENTIMENT_ALIASES.get(sentiment, sentiment),
        intensity=intensity,
        animation_trigger=trigger if trigger in ANIMATION_TRIGGERS else "idle_listen",
    )


def _error_detail(res: httpx.Response) -> str:
    try:
        err = res.json().get("error")
    except ValueError:
        return res.text[:200]
    if isinstance(err, dict):
        return str(err.get("message", err))
    return str(err)


class OpenAICompatQwenClient:
    """Qwen over any OpenAI-compatible chat completions API (Ollama, DashScope, vLLM).

    Reliability, in order:
    1. Ask for output matching RESPONSE_SCHEMA (`json_mode="schema"`). If the
       server rejects that with a 400, drop to plain JSON mode for good.
    2. If the reply still doesn't parse, retry once at temperature 0.
    3. Otherwise return FALLBACK_ANALYSIS with `fallback_reason` set, so the
       chat keeps working and the reason shows up in the logs and UI.
    """

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 120.0,
        json_mode: Literal["schema", "object", "none"] = "schema",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.json_mode = json_mode
        self._transport = transport  # tests inject httpx.MockTransport

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, transport=self._transport)

    def _response_format(self) -> dict | None:
        if self.json_mode == "schema":
            return {
                "type": "json_schema",
                "json_schema": {"name": "intake_reply", "strict": True, "schema": RESPONSE_SCHEMA},
            }
        if self.json_mode == "object":
            return {"type": "json_object"}
        return None

    def _messages(self, message: str, history: Sequence[Turn]) -> list[dict[str, str]]:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
        msgs += [{"role": t.role, "content": t.text} for t in history[-HISTORY_TURNS:]]
        msgs.append({"role": "user", "content": message})
        return msgs

    async def _complete(self, client: httpx.AsyncClient, messages: list, temperature: float) -> str:
        payload: dict = {"model": self.model, "messages": messages, "temperature": temperature}
        if (fmt := self._response_format()) is not None:
            payload["response_format"] = fmt
        url = f"{self.base_url}/chat/completions"
        try:
            res = await client.post(url, json=payload, headers=self._headers)
        except httpx.ConnectError as exc:
            raise LLMUnavailable(
                f"Can't reach the model server at {self.base_url}. Is Ollama running? "
                "Start the Ollama app (or run `ollama serve`) and try again."
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMUnavailable(
                f"The model took longer than {self.timeout:.0f}s. The first reply after "
                "starting Ollama loads the model and is slow; try again, or use a smaller "
                "model / raise LLM_TIMEOUT_SECONDS."
            ) from exc

        if res.status_code == 400 and self.json_mode == "schema":
            logger.warning("Server rejected json_schema output (%s); using JSON mode", _error_detail(res))
            self.json_mode = "object"
            return await self._complete(client, messages, temperature)
        if res.status_code == 404:
            raise LLMUnavailable(
                f"Model '{self.model}' not found on {self.base_url} ({_error_detail(res)}). "
                f"Run: ollama pull {self.model}"
            )
        if res.status_code in (401, 403):
            raise LLMUnavailable(f"The model server rejected the API key ({res.status_code}). Check LLM_API_KEY.")
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]

    async def analyze(self, message: str, history: Sequence[Turn] = ()) -> ModelAnalysis:
        messages = self._messages(message, history)
        reason = "unknown error"
        try:
            async with self._client() as client:
                for attempt, temperature in enumerate((0.4, 0.0)):
                    try:
                        content = await self._complete(client, messages, temperature)
                        return parse_model_json(content)
                    except httpx.HTTPStatusError as exc:
                        reason = f"model server error {exc.response.status_code}: {_error_detail(exc.response)}"
                    except (KeyError, IndexError, TypeError, ValueError) as exc:
                        reason = f"unusable model output: {exc}"
                    logger.warning("LLM attempt %d failed: %s", attempt + 1, reason)
        except LLMUnavailable as exc:
            reason = str(exc)
        except httpx.HTTPError as exc:
            reason = f"model request failed: {exc!r}"
        logger.error("Using fallback reply. %s", reason)
        return ModelAnalysis(**{**FALLBACK_ANALYSIS.__dict__, "fallback_reason": reason})

    async def check(self) -> dict:
        """Preflight for /api/v1/status: is the server up and the model available?"""
        try:
            async with self._client() as client:
                res = await client.get(f"{self.base_url}/models", headers=self._headers, timeout=5)
            res.raise_for_status()
            names = [m.get("id") for m in res.json().get("data", [])]
        except httpx.ConnectError:
            return {"ok": False, "detail": f"Can't reach {self.base_url}. Is Ollama running?"}
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            return {"ok": False, "detail": f"Model list failed: {exc!r}"}
        # Ollama lists "qwen2.5:7b"; a bare "qwen2.5" means ":latest".
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        if names and wanted not in names and self.model not in names:
            return {
                "ok": False,
                "detail": f"Model '{self.model}' isn't pulled. Run: ollama pull {self.model}",
                "available": names,
            }
        return {"ok": True, "detail": f"{self.model} at {self.base_url}"}


DEFAULT_MODEL = "qwen2.5:1.5b"


@lru_cache
def _openai_client_from_env() -> OpenAICompatQwenClient:
    return OpenAICompatQwenClient(
        base_url=os.getenv("LLM_BASE_URL", "http://127.0.0.1:11434/v1"),
        model=os.getenv("LLM_MODEL", DEFAULT_MODEL),
        api_key=os.getenv("LLM_API_KEY") or None,
        timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
        json_mode=os.getenv("LLM_JSON_MODE", "schema"),  # type: ignore[arg-type]
    )


def get_llm_client() -> LLMClient:
    """FastAPI dependency. Tests replace it via `app.dependency_overrides`."""
    provider = os.getenv("LLM_PROVIDER", "stub")
    if provider == "stub":
        return StubQwenClient()
    if provider == "openai":
        return _openai_client_from_env()
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider!r}")
