"""Speech-to-text layer, same pattern as `qwen_service`.

- `StubTranscriber`: returns a fixed phrase. Default, used by tests and CI.
- `FasterWhisperTranscriber`: local Whisper via faster-whisper (CTranslate2),
  CPU int8 by default. Install with `pip install -r requirements-voice.txt`.

Select with `STT_PROVIDER` (`stub` | `faster-whisper`), see `get_transcriber`.
"""

import asyncio
import io
import logging
import os
import threading
from functools import lru_cache
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


class STTUnavailable(Exception):
    """The speech model can't be loaded. `str()` says how to fix it."""


class AudioDecodeError(Exception):
    """The upload isn't audio we can decode."""


class Transcriber(Protocol):
    async def transcribe(self, audio: bytes) -> str: ...


class StubTranscriber:
    """Ignores the audio. Lets the voice UI be exercised without a model."""

    def __init__(self, text: str = "I've been feeling anxious about my exams"):
        self.text = text

    async def transcribe(self, audio: bytes) -> str:
        return self.text

    def status(self) -> dict:
        return {"ok": True, "detail": "stub (fixed phrase, audio ignored)"}


# Segments Whisper itself thinks are probably not speech. On near-silent clips
# it otherwise invents phrases like "Thank you for watching."
NO_SPEECH_PROB = 0.6
MIN_AVG_LOGPROB = -1.0


def _whisper_model(model_size: str, device: str, compute_type: str) -> Any:
    # Imported here so the API (and CI) runs without the heavy dependency.
    from faster_whisper import WhisperModel

    return WhisperModel(model_size, device=device, compute_type=compute_type)


def _decode(audio: bytes) -> Any:
    from faster_whisper import decode_audio

    # PyAV (bundled with faster-whisper) decodes webm/ogg/mp4/wav/mp3, no system FFmpeg needed.
    return decode_audio(io.BytesIO(audio))


class FasterWhisperTranscriber:
    """Whisper on the local machine. The model downloads on first load (roughly 0.5 GB for `small`)."""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str | None = "en",
        beam_size: int = 5,
        model_factory: Callable[[str, str, str], Any] = _whisper_model,
        decoder: Callable[[bytes], Any] = _decode,
    ):
        self.model_size, self.device, self.compute_type = model_size, device, compute_type
        self.language = language  # None = auto-detect (slower, less reliable on short clips)
        self.beam_size = beam_size
        self._factory = model_factory
        self._decode = decoder
        self._model: Any = None
        self._error: str | None = None
        self._lock = threading.Lock()

    def load(self) -> None:
        """Load (and on first run download) the model. Safe to call repeatedly."""
        with self._lock:
            if self._model is not None:
                return
            logger.info("Loading Whisper '%s' on %s (%s)...", self.model_size, self.device, self.compute_type)
            try:
                self._model = self._factory(self.model_size, self.device, self.compute_type)
                self._error = None
                logger.info("Whisper '%s' ready", self.model_size)
            except Exception as exc:  # download, disk, CUDA, corrupt cache...
                self._error = (
                    f"Couldn't load Whisper '{self.model_size}' on {self.device}: {exc}. "
                    "The first run downloads it from huggingface.co, so check your internet "
                    "connection. On an NVIDIA GPU without CUDA 12 + cuDNN 9, use STT_DEVICE=cpu."
                )
                logger.error(self._error)
                raise STTUnavailable(self._error) from exc

    def status(self) -> dict:
        if self._model is not None:
            return {"ok": True, "detail": f"Whisper {self.model_size} loaded ({self.device}, {self.compute_type})"}
        if self._error:
            return {"ok": False, "detail": self._error}
        return {"ok": False, "detail": f"Whisper {self.model_size} still loading (first run downloads it)"}

    def _transcribe_sync(self, audio: bytes) -> str:
        self.load()
        try:
            samples = self._decode(audio)
        except Exception as exc:
            raise AudioDecodeError(f"Couldn't decode the recording: {exc}") from exc
        segments, _info = self._model.transcribe(
            samples,
            language=self.language,
            beam_size=self.beam_size,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        kept = [
            s.text.strip()
            for s in segments
            if not (s.no_speech_prob > NO_SPEECH_PROB and s.avg_logprob < MIN_AVG_LOGPROB)
        ]
        return " ".join(t for t in kept if t).strip()

    async def transcribe(self, audio: bytes) -> str:
        # Whisper is CPU-bound; keep it off the event loop.
        return await asyncio.to_thread(self._transcribe_sync, audio)


@lru_cache
def _whisper_from_env() -> FasterWhisperTranscriber:
    language = os.getenv("STT_LANGUAGE", "en")
    return FasterWhisperTranscriber(
        model_size=os.getenv("STT_MODEL", "small"),
        device=os.getenv("STT_DEVICE", "cpu"),
        compute_type=os.getenv("STT_COMPUTE_TYPE", "int8"),
        language=None if language == "auto" else language,
        beam_size=int(os.getenv("STT_BEAM_SIZE", "5")),
    )


def get_transcriber() -> Transcriber:
    """FastAPI dependency. Tests replace it via `app.dependency_overrides`."""
    provider = os.getenv("STT_PROVIDER", "stub")
    if provider == "stub":
        return StubTranscriber()
    if provider == "faster-whisper":
        return _whisper_from_env()
    raise RuntimeError(f"Unsupported STT_PROVIDER: {provider!r}")
