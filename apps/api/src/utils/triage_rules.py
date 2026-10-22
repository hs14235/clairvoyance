"""Clinical triage rules. These own the takeover decision, not the model."""

from src.schemas import Sentiment
from src.services.qwen_service import ModelAnalysis

TAKEOVER_INTENSITY_THRESHOLD = 8
MIN_INTENSITY, MAX_INTENSITY = 1, 10

# Phrases that force a human takeover regardless of the model's score.
CRISIS_KEYWORDS = (
    "kill myself",
    "suicide",
    "suicidal",
    "end my life",
    "want to die",
    "hurt myself",
    "self harm",
    "self-harm",
)


def normalize_intensity(raw: int) -> int:
    """Clamp a model-supplied intensity into the 1-10 scale."""
    return max(MIN_INTENSITY, min(MAX_INTENSITY, int(raw)))


def normalize_sentiment(raw: str) -> Sentiment:
    """Map an unknown model label to neutral instead of failing the request."""
    try:
        return Sentiment(raw.lower())
    except ValueError:
        return Sentiment.neutral


def contains_crisis_language(message: str) -> bool:
    text = message.lower()
    return any(k in text for k in CRISIS_KEYWORDS)


def requires_human_takeover(intensity: int, message: str) -> bool:
    return intensity >= TAKEOVER_INTENSITY_THRESHOLD or contains_crisis_language(message)


def evaluate(message: str, analysis: ModelAnalysis) -> tuple[Sentiment, int, bool]:
    """Return validated (sentiment, intensity, human_takeover_flag)."""
    intensity = normalize_intensity(analysis.intensity)
    sentiment = normalize_sentiment(analysis.sentiment)
    return sentiment, intensity, requires_human_takeover(intensity, message)
