import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.services.qwen_service import ModelAnalysis, StubQwenClient, get_llm_client
from src.utils import triage_rules

URL = "/api/v1/chat/message"


class FixedClient:
    """Fake model that returns whatever analysis the test hands it."""

    def __init__(self, analysis: ModelAnalysis):
        self.analysis = analysis

    async def analyze(self, message: str, history=()) -> ModelAnalysis:
        return self.analysis


def fixed(intensity: int, sentiment: str = "anxious") -> FixedClient:
    return FixedClient(ModelAnalysis("ok", sentiment, intensity, "supportive_nod"))


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_model(fake) -> None:
    app.dependency_overrides[get_llm_client] = lambda: fake


# --- endpoint contract ---

def test_returns_full_payload(client):
    res = client.post(URL, json={"message": "I'm feeling anxious about exams"})
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {
        "text_response", "sentiment", "intensity", "animation_trigger",
        "human_takeover_flag", "session_id", "ai_paused", "model_fallback",
    }
    assert body["ai_paused"] is False
    assert body["sentiment"] == "anxious"
    assert body["intensity"] == 4
    assert body["human_takeover_flag"] is False


@pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": 123}])
def test_rejects_invalid_body(client, payload):
    assert client.post(URL, json=payload).status_code == 422


# --- takeover threshold, enforced by rules not the model ---

@pytest.mark.parametrize("intensity,expected", [(1, False), (7, False), (8, True), (9, True), (10, True)])
def test_takeover_threshold(client, intensity, expected):
    use_model(fixed(intensity))
    body = client.post(URL, json={"message": "hello"}).json()
    assert body["intensity"] == intensity
    assert body["human_takeover_flag"] is expected


@pytest.mark.parametrize("raw,clamped,flag", [(42, 10, True), (-3, 1, False), (0, 1, False)])
def test_out_of_range_intensity_is_clamped(client, raw, clamped, flag):
    use_model(fixed(raw))
    body = client.post(URL, json={"message": "hello"}).json()
    assert body["intensity"] == clamped
    assert body["human_takeover_flag"] is flag


def test_crisis_language_forces_takeover_even_if_model_scores_low(client):
    use_model(fixed(2, "calm"))
    body = client.post(URL, json={"message": "honestly I want to die"}).json()
    assert body["intensity"] == 2
    assert body["human_takeover_flag"] is True


def test_unknown_sentiment_falls_back_to_neutral(client):
    use_model(fixed(3, "melancholic"))
    assert client.post(URL, json={"message": "hi"}).json()["sentiment"] == "neutral"


def test_stub_high_distress_triggers_takeover(client):
    body = client.post(URL, json={"message": "I feel hopeless"}).json()
    assert body["sentiment"] == "distressed"
    assert body["human_takeover_flag"] is True


# --- unit level ---

def test_rules_boundary():
    assert triage_rules.requires_human_takeover(7, "hi") is False
    assert triage_rules.requires_human_takeover(8, "hi") is True


async def _analyze(msg):
    return await StubQwenClient().analyze(msg)


def test_stub_is_deterministic():
    import asyncio

    a = asyncio.run(_analyze("I'm so stressed"))
    b = asyncio.run(_analyze("I'm so stressed"))
    assert a == b


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


# --- CORS ---

def test_cors_allows_local_web_app(client):
    res = client.options(
        URL,
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unknown_origin(client):
    res = client.post(
        URL, json={"message": "hi"}, headers={"Origin": "https://evil.example"}
    )
    assert "access-control-allow-origin" not in res.headers
