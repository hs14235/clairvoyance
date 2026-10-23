"""Speech-to-text layer, same pattern as `qwen_service`.

- `StubTranscriber`: returns a fixed phrase. Default, used by tests and CI.
- `FasterWhisperTranscriber`: local Whisper via faster-whisper (CTranslate2),
  CPU int8 by default. Install with `pip install -r requirements-voice.txt`.

Select with `STT_PROVIDER` (`stub` | `faster-whisper`), see `get_transcriber`.
"""

import asyncio
import io
import os
from functools import lru_cache
from typing import Protocol


class Transcriber(Protocol):
    async def transcribe(self, audio: bytes) -> str: ...


class StubTranscriber:
    """Ignores the audio. Lets the voice UI be exercised without a model."""

    def __init__(self, text: str = "I've been feeling anxious about my exams"):
        self.text = text

    async def transcribe(self, audio: bytes) -> str:
        return self.text


class FasterWhisperTranscriber:
    """Whisper on the local machine. The model downloads on first use (roughly 0.5 GB for `small`)."""

    def __init__(self, model_size: str = "small", device: str = "cpu", compute_type: str = "int8"):
        # Imported here so the API (and CI) runs without the heavy dependency.
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.language = os.getenv("STT_LANGUAGE") or None  # None = auto-detect

    def _transcribe_sync(self, audio: bytes) -> str:
        # PyAV (bundled with faster-whisper) decodes webm/ogg/wav/mp3, no system FFmpeg needed.
        segments, _info = self.model.transcribe(
            io.BytesIO(audio), language=self.language, beam_size=1, vad_filter=True
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    async def transcribe(self, audio: bytes) -> str:
        # Whisper is CPU-bound; keep it off the event loop.
        return await asyncio.to_thread(self._transcribe_sync, audio)


@lru_cache
def _whisper_from_env() -> FasterWhisperTranscriber:
    return FasterWhisperTranscriber(
        model_size=os.getenv("STT_MODEL", "small"),
        device=os.getenv("STT_DEVICE", "cpu"),
        compute_type=os.getenv("STT_COMPUTE_TYPE", "int8"),
    )


def get_transcriber() -> Transcriber:
    """FastAPI dependency. Tests replace it via `app.dependency_overrides`."""
    provider = os.getenv("STT_PROVIDER", "stub")
    if provider == "stub":
        return StubTranscriber()
    if provider == "faster-whisper":
        return _whisper_from_env()
    raise RuntimeError(f"Unsupported STT_PROVIDER: {provider!r}")
