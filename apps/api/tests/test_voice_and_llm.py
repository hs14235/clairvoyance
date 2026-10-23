import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.routers.chat import CRISIS_FALLBACK_REPLY
from src.services import qwen_service
from src.services.qwen_service import (
    FALLBACK_ANALYSIS,
    HISTORY_TURNS,
    RESPONSE_SCHEMA,
    ModelAnalysis,
    OpenAICompatQwenClient,
    Turn,
    get_llm_client,
    parse_model_json,
)
from src.services.speech_service import FasterWhisperTranscriber, StubTranscriber, get_transcriber

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

GOOD = json.dumps({
    "text_response": "That sounds stressful.",
    "sentiment": "anxious",
    "intensity": 5,
    "animation_trigger": "supportive_nod",
})


def test_qwen_client_sends_schema_request_with_history_and_parses_reply():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=completion(GOOD))

    history = [Turn("user", "hi"), Turn("assistant", "Hello, how are you?")]
    result = run(qwen_with(handler).analyze("exams are killing me", history))

    assert result == ModelAnalysis("That sounds stressful.", "anxious", 5, "supportive_nod")
    assert result.fallback_reason is None
    assert seen["url"] == "http://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer secret"
    body = seen["body"]
    assert body["model"] == "qwen2.5:3b"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["schema"] == RESPONSE_SCHEMA
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert body["messages"][-1]["content"] == "exams are killing me"


def test_history_is_capped():
    seen = {}

    def handler(request):
        seen["n"] = len(json.loads(request.content)["messages"])
        return httpx.Response(200, json=completion(GOOD))

    history = [Turn("user", f"m{i}") for i in range(30)]
    run(qwen_with(handler).analyze("now", history))
    assert seen["n"] == 1 + HISTORY_TURNS + 1


def test_qwen_client_omits_auth_header_without_key():
    def handler(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, json=completion('{"text_response": "hi"}'))

    client = OpenAICompatQwenClient("http://llm.test/v1", "m", transport=httpx.MockTransport(handler))
    assert run(client.analyze("hey")).text_response == "hi"


def test_schema_rejected_downgrades_to_json_mode_once():
    formats = []

    def handler(request):
        fmt = json.loads(request.content).get("response_format", {}).get("type")
        formats.append(fmt)
        if fmt == "json_schema":
            return httpx.Response(400, json={"error": {"message": "unsupported response_format"}})
        return httpx.Response(200, json=completion(GOOD))

    llm = qwen_with(handler)
    assert run(llm.analyze("a")).fallback_reason is None
    assert run(llm.analyze("b")).fallback_reason is None
    assert formats == ["json_schema", "json_object", "json_object"]


def test_bad_json_is_retried_once_at_temperature_zero():
    temps = []

    def handler(request):
        temps.append(json.loads(request.content)["temperature"])
        content = "Sure! Here you go" if len(temps) == 1 else GOOD
        return httpx.Response(200, json=completion(content))

    result = run(qwen_with(handler).analyze("hello"))
    assert result.text_response == "That sounds stressful."
    assert temps == [0.4, 0.0]


@pytest.mark.parametrize("handler,reason", [
    (lambda r: httpx.Response(500, text="boom"), "model server error 500"),
    (lambda r: httpx.Response(200, json=completion("Sorry, no JSON today.")), "unusable model output"),
    (lambda r: httpx.Response(200, json={"unexpected": True}), "unusable model output"),
    (lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused")), "Is Ollama running?"),
    (lambda r: (_ for _ in ()).throw(httpx.ReadTimeout("slow")), "LLM_TIMEOUT_SECONDS"),
    (lambda r: httpx.Response(401, json={"error": "bad key"}), "LLM_API_KEY"),
    (
        lambda r: httpx.Response(404, json={"error": {"message": 'model "qwen2.5:3b" not found, try pulling it first'}}),
        "Run: ollama pull qwen2.5:3b",
    ),
])
def test_qwen_client_falls_back_with_actionable_reason(handler, reason):
    result = run(qwen_with(handler).analyze("hello"))
    assert result.text_response == FALLBACK_ANALYSIS.text_response
    assert reason in result.fallback_reason


def test_unavailable_server_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404, json={"error": "model 'x' not found"})

    run(qwen_with(handler).analyze("hello"))
    assert len(calls) == 1


def test_parse_model_json_tolerates_fences_aliases_and_bad_values():
    raw = '```json\n{"text_response": " ok ", "sentiment": "Anxiety", "intensity": "high", "animation_trigger": "dance"}\n```'
    assert parse_model_json(raw) == ModelAnalysis("ok", "anxious", 1, "idle_listen")


@pytest.mark.parametrize("raw", ['{"text_response": "", "intensity": 3}', "[1, 2]", "{not json}"])
def test_parse_model_json_rejects_unusable(raw):
    with pytest.raises(ValueError):
        parse_model_json(raw)


def test_fallback_still_escalates_crisis_language_and_is_flagged(client):
    app.dependency_overrides[get_llm_client] = lambda: qwen_with(lambda r: httpx.Response(503))
    body = client.post(CHAT_URL, json={"message": "I want to die"}).json()
    assert body["text_response"] == CRISIS_FALLBACK_REPLY
    assert body["animation_trigger"] == "concerned_lean_in"
    assert body["human_takeover_flag"] is True
    assert body["model_fallback"] is True


def test_fallback_without_crisis_uses_neutral_line(client):
    app.dependency_overrides[get_llm_client] = lambda: qwen_with(lambda r: httpx.Response(503))
    body = client.post(CHAT_URL, json={"message": "hi there"}).json()
    assert body["text_response"] == FALLBACK_ANALYSIS.text_response
    assert body["human_takeover_flag"] is False
    assert body["model_fallback"] is True


def test_model_cannot_skip_takeover_threshold(client):
    def handler(r):
        return httpx.Response(200, json=completion(
            '{"text_response": "ok", "sentiment": "distressed", "intensity": 9}'))

    app.dependency_overrides[get_llm_client] = lambda: qwen_with(handler)
    body = client.post(CHAT_URL, json={"message": "everything is falling apart"}).json()
    assert body["intensity"] == 9
    assert body["human_takeover_flag"] is True
    assert body["model_fallback"] is False


def test_chat_sends_session_history_to_model(client):
    seen = []

    def handler(request):
        seen.append([m["content"] for m in json.loads(request.content)["messages"][1:]])
        return httpx.Response(200, json=completion(GOOD))

    llm = qwen_with(handler)
    app.dependency_overrides[get_llm_client] = lambda: llm
    sid = client.post(CHAT_URL, json={"message": "first"}).json()["session_id"]
    client.post(CHAT_URL, json={"message": "second", "session_id": sid})
    assert seen[0] == ["first"]
    assert seen[1] == ["first", "That sounds stressful.", "second"]


def test_provider_selection(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")
    qwen_service._openai_client_from_env.cache_clear()
    llm = get_llm_client()
    assert isinstance(llm, OpenAICompatQwenClient)
    assert llm.model == "qwen2.5:7b"
    assert llm.base_url == "http://127.0.0.1:11434/v1"
    qwen_service._openai_client_from_env.cache_clear()

    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(RuntimeError):
        get_llm_client()


def test_default_model_is_apache_licensed(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    qwen_service._openai_client_from_env.cache_clear()
    assert get_llm_client().model == "qwen2.5:1.5b"
    qwen_service._openai_client_from_env.cache_clear()


@pytest.mark.parametrize("models,ok,text", [
    ({"data": [{"id": "qwen2.5:3b"}]}, True, "qwen2.5:3b"),
    ({"data": [{"id": "llama3.2:latest"}]}, False, "ollama pull qwen2.5:3b"),
])
def test_check_reports_missing_model(models, ok, text):
    llm = qwen_with(lambda r: httpx.Response(200, json=models))
    result = run(llm.check())
    assert result["ok"] is ok
    assert text in result["detail"]


def test_check_reports_server_down():
    llm = qwen_with(lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused")))
    result = run(llm.check())
    assert result["ok"] is False
    assert "Is Ollama running?" in result["detail"]


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


# --- faster-whisper wrapper (fake model, no download) ---

class FakeSegment:
    def __init__(self, text, no_speech_prob=0.0, avg_logprob=-0.2):
        self.text, self.no_speech_prob, self.avg_logprob = text, no_speech_prob, avg_logprob


class FakeWhisper:
    def __init__(self, segments):
        self.segments = segments
        self.kwargs = None

    def transcribe(self, samples, **kwargs):
        self.kwargs = kwargs
        return iter(self.segments), None


def whisper_with(model=None, factory_error=None, decode_error=None):
    def factory(size, device, compute):
        if factory_error:
            raise factory_error
        return model

    def decode(audio):
        if decode_error:
            raise decode_error
        return [0.0] * 16000

    return FasterWhisperTranscriber(model_factory=factory, decoder=decode)


def test_whisper_joins_segments_and_drops_hallucinated_silence():
    model = FakeWhisper([
        FakeSegment(" I can't sleep "),
        FakeSegment("Thank you for watching.", no_speech_prob=0.9, avg_logprob=-1.5),
        FakeSegment(" before exams."),
    ])
    stt = whisper_with(model)
    assert run(stt.transcribe(b"x")) == "I can't sleep before exams."
    assert model.kwargs["language"] == "en"
    assert model.kwargs["vad_filter"] is True
    assert stt.status()["ok"] is True


def test_whisper_load_failure_is_503_with_fix(client):
    stt = whisper_with(factory_error=OSError("connection refused"))
    app.dependency_overrides[get_transcriber] = lambda: stt
    res = client.post(TRANSCRIBE_URL, files={"audio": ("a.webm", b"abc", "audio/webm")})
    assert res.status_code == 503
    assert "huggingface.co" in res.json()["detail"]
    assert stt.status()["ok"] is False


def test_undecodable_audio_is_422(client):
    stt = whisper_with(FakeWhisper([]), decode_error=ValueError("Invalid data found"))
    app.dependency_overrides[get_transcriber] = lambda: stt
    res = client.post(TRANSCRIBE_URL, files={"audio": ("a.webm", b"abc", "audio/webm")})
    assert res.status_code == 422
    assert "decode" in res.json()["detail"]


def test_real_decoder_reads_wav_and_rejects_garbage():
    pytest.importorskip("faster_whisper")
    import io
    import math
    import struct
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(i / 10))) for i in range(16000)))
    from src.services.speech_service import _decode

    assert len(_decode(buf.getvalue())) == 16000
    with pytest.raises(Exception):
        _decode(b"definitely not audio")


# --- status endpoint ---

def test_status_with_stubs(client):
    body = client.get("/api/v1/status").json()
    assert body["llm"]["ok"] is True and body["llm"]["provider"] == "stub"
    assert body["stt"]["ok"] is True


def test_status_reports_ollama_down(client):
    app.dependency_overrides[get_llm_client] = lambda: qwen_with(
        lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused")))
    body = client.get("/api/v1/status").json()
    assert body["llm"]["ok"] is False
    assert "Ollama" in body["llm"]["detail"]
