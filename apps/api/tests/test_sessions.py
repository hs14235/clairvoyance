import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.qwen_service import ModelAnalysis
from src.services.qwen_service import get_llm_client
from src.services.session_store import SessionStore, get_session_store

CHAT = "/api/v1/chat/message"
SESSIONS = "/api/v1/sessions"


class CountingClient:
    """Stub-like fake that records how often the model was called."""

    def __init__(self, intensity: int = 3):
        self.calls = 0
        self.intensity = intensity

    async def analyze(self, message: str) -> ModelAnalysis:
        self.calls += 1
        return ModelAnalysis("ai reply", "anxious", self.intensity, "supportive_nod")


@pytest.fixture
def store():
    fresh = SessionStore()
    app.dependency_overrides[get_session_store] = lambda: fresh
    yield fresh
    app.dependency_overrides.clear()


@pytest.fixture
def client(store):
    return TestClient(app)


def chat(client, sid, message):
    return client.post(CHAT, json={"message": message, "session_id": sid}).json()


def test_chat_records_history_and_latest_metrics(client):
    chat(client, "s1", "I'm a bit stressed")
    chat(client, "s1", "I feel hopeless")

    body = client.get(f"{SESSIONS}/s1").json()
    assert [m["role"] for m in body["messages"]] == ["client", "ai", "client", "ai"]
    assert body["messages"][0]["text"] == "I'm a bit stressed"
    assert body["sentiment"] == "distressed"
    assert body["intensity"] == 9
    assert body["peak_intensity"] == 9
    assert body["status"] == "flagged"
    assert body["flagged_at"] is not None


def test_session_id_generated_when_missing(client):
    body = client.post(CHAT, json={"message": "hi"}).json()
    assert body["session_id"]
    assert client.get(f"{SESSIONS}/{body['session_id']}").status_code == 200


def test_flag_is_sticky_after_calmer_message(client):
    chat(client, "s1", "I want to die")
    chat(client, "s1", "ok I feel better now")
    body = client.get(f"{SESSIONS}/s1").json()
    assert body["status"] == "flagged"
    assert body["intensity"] == 2
    assert body["peak_intensity"] >= 2


def test_list_puts_flagged_first_then_counselor_then_ai(client):
    chat(client, "calm-old", "hello")
    chat(client, "flagged", "I feel hopeless")
    chat(client, "held", "hello")
    client.post(f"{SESSIONS}/held/takeover")
    chat(client, "calm-new", "hello")

    ids = [s["id"] for s in client.get(SESSIONS).json()]
    assert ids == ["flagged", "held", "calm-new", "calm-old"]


def test_list_summary_fields(client):
    chat(client, "s1", "hello")
    [summary] = client.get(SESSIONS).json()
    assert summary["message_count"] == 2
    assert summary["last_client_message"] == "hello"  # client text, not the AI reply
    assert "messages" not in summary


def test_takeover_stops_ai_replies(client):
    fake = CountingClient()
    app.dependency_overrides[get_llm_client] = lambda: fake

    chat(client, "s1", "hello")
    assert fake.calls == 1

    res = client.post(f"{SESSIONS}/s1/takeover")
    assert res.status_code == 200
    assert res.json()["status"] == "counselor"

    body = chat(client, "s1", "are you still there?")
    assert fake.calls == 1  # model not called
    assert body["ai_paused"] is True
    assert body["human_takeover_flag"] is True
    assert body["text_response"] != "ai reply"

    roles = [m["role"] for m in client.get(f"{SESSIONS}/s1").json()["messages"]]
    assert roles == ["client", "ai", "client"]  # client message still logged


def test_crisis_language_while_paused_still_flags(client, store):
    chat(client, "s1", "hello")
    client.post(f"{SESSIONS}/s1/takeover")
    chat(client, "s1", "I want to hurt myself")
    assert store.get("s1").flagged_at is not None


def test_takeover_is_idempotent(client):
    chat(client, "s1", "hello")
    first = client.post(f"{SESSIONS}/s1/takeover").json()
    second = client.post(f"{SESSIONS}/s1/takeover").json()
    assert first["taken_over_at"] == second["taken_over_at"]


def test_release_returns_session_to_ai(client):
    fake = CountingClient()
    app.dependency_overrides[get_llm_client] = lambda: fake
    chat(client, "s1", "hello")
    client.post(f"{SESSIONS}/s1/takeover")

    assert client.post(f"{SESSIONS}/s1/release").json()["status"] == "ai"
    body = chat(client, "s1", "hello again")
    assert body["ai_paused"] is False
    assert fake.calls == 2


def test_release_keeps_flag(client):
    chat(client, "s1", "I feel hopeless")
    client.post(f"{SESSIONS}/s1/takeover")
    assert client.post(f"{SESSIONS}/s1/release").json()["status"] == "flagged"


@pytest.mark.parametrize("path", ["", "/takeover", "/release"])
def test_unknown_session_404(client, path):
    method = client.get if path == "" else client.post
    assert method(f"{SESSIONS}/nope{path}").status_code == 404


def test_rejects_overlong_session_id(client):
    res = client.post(CHAT, json={"message": "hi", "session_id": "x" * 129})
    assert res.status_code == 422
