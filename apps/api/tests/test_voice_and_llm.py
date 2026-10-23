import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services import qwen_service
from src.services.qwen_service import (
    FALLBACK_ANALYSIS,
    ModelAnalysis,
    OpenAICompatQwenClient,
    get_llm_client,
    parse_model_json,
)
from src.services.speech_service import StubTranscriber, get_transcriber

TRANSCRIBE_URL = "/api/v1/speech/transcribe"
CHAT_URL = "/api/v1/chat/message"


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def completion(content: str) -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def qwen_with(handler) -> OpenAICompatQwenClient:
    return OpenAICompatQwenClient(
        base_url="http://llm.test/v1/",
        model="qwen2.5:3b",
        api_key="secret",
        transport=httpx.MockTransport(handler),
    )


def run(coro):
    return asyncio.run(coro)


# --- OpenAI-compatible Qwen client ---

def test_qwen_client_sends_openai_request_and_parses_reply():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=completion(json.dumps({
            "text_response": "That sounds stressful.",
            "sentiment": "anxious",
            "intensity": 5,
            "animation_trigger": "supportive_nod",
        })))

    result = run(qwen_with(handler).analyze("exams are killing me"))

    assert result == ModelAnalysis("That sounds stressful.", "anxious", 5, "supportive_nod")
    assert seen["url"] == "http://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer secret"
    assert seen["body"]["model"] == "qwen2.5:3b"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert seen["body"]["messages"][-1] == {"role": "user", "content": "exams are killing me"}


def test_qwen_client_omits_auth_header_without_key():
    def handler(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, json=completion('{"text_response": "hi"}'))

    client = OpenAICompatQwenClient("http://llm.test/v1", "m", transport=httpx.MockTransport(handler))
    assert run(client.analyze("hey")).text_response == "hi"


@pytest.mark.parametrize("handler", [
    lambda r: httpx.Response(500, text="boom"),
    lambda r: httpx.Response(200, json=completion("Sorry, I can't do JSON today.")),
    lambda r: httpx.Response(200, json={"unexpected": True}),
    lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused")),
])
def test_qwen_client_falls_back_instead_of_failing(handler):
    assert run(qwen_with(handler).analyze("hello")) == FALLBACK_ANALYSIS


def test_parse_model_json_tolerates_fences_and_bad_intensity():
    raw = '```json\n{"text_response": " ok ", "sentiment": "sad", "intensity": "high"}\n```'
    assert parse_model_json(raw) == ModelAnalysis("ok", "sad", 1, "idle_listen")


def test_parse_model_json_rejects_empty_text():
    with pytest.raises(ValueError):
        parse_model_json('{"text_response": "", "intensity": 3}')


def test_fallback_still_escalates_crisis_language(client):
    app.dependency_overrides[get_llm_client] = lambda: qwen_with(lambda r: httpx.Response(503))
    body = client.post(CHAT_URL, json={"message": "I want to die"}).json()
    assert body["text_response"] == FALLBACK_ANALYSIS.text_response
    assert body["human_takeover_flag"] is True


def test_model_cannot_skip_takeover_threshold(client):
    def handler(r):
        return httpx.Response(200, json=completion(
            '{"text_response": "ok", "sentiment": "distressed", "intensity": 9}'))

    app.dependency_overrides[get_llm_client] = lambda: qwen_with(handler)
    body = client.post(CHAT_URL, json={"message": "everything is falling apart"}).json()
    assert body["intensity"] == 9
    assert body["human_takeover_flag"] is True


def test_provider_selection(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")
    qwen_service._openai_client_from_env.cache_clear()
    llm = get_llm_client()
    assert isinstance(llm, OpenAICompatQwenClient)
    assert llm.model == "qwen2.5:7b"
    assert llm.base_url == "http://localhost:11434/v1"
    qwen_service._openai_client_from_env.cache_clear()

    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(RuntimeError):
        get_llm_client()


# --- speech-to-text endpoint ---

def test_transcribe_returns_text(client):
    app.dependency_overrides[get_transcriber] = lambda: StubTranscriber("hello there")
    res = client.post(TRANSCRIBE_URL, files={"audio": ("clip.webm", b"\x1aE\xdf\xa3fake", "audio/webm")})
    assert res.status_code == 200
    assert res.json() == {"text": "hello there"}


def test_transcribe_default_is_stub(client):
    res = client.post(TRANSCRIBE_URL, files={"audio": ("clip.webm", b"abc", "audio/webm")})
    assert res.status_code == 200
    assert res.json()["text"]


def test_transcribe_rejects_empty_and_missing_audio(client):
    assert client.post(TRANSCRIBE_URL, files={"audio": ("clip.webm", b"", "audio/webm")}).status_code == 422
    assert client.post(TRANSCRIBE_URL).status_code == 422


def test_transcribe_rejects_oversized_audio(client, monkeypatch):
    monkeypatch.setattr("src.routers.speech.MAX_AUDIO_BYTES", 10)
    res = client.post(TRANSCRIBE_URL, files={"audio": ("clip.webm", b"x" * 11, "audio/webm")})
    assert res.status_code == 413


def test_voice_round_trip_feeds_chat(client):
    """Transcript from /speech goes to /chat unchanged: the full loop with stubs."""
    app.dependency_overrides[get_transcriber] = lambda: StubTranscriber("I feel hopeless")
    text = client.post(TRANSCRIBE_URL, files={"audio": ("a.webm", b"abc", "audio/webm")}).json()["text"]
    body = client.post(CHAT_URL, json={"message": text}).json()
    assert body["sentiment"] == "distressed"
    assert body["human_takeover_flag"] is True
