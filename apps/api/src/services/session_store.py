"""Session tracking for the counselor dashboard.

In-memory only: state is lost on restart and is not shared between workers.
PostgreSQL (history) and Redis (live state) replace this later; keep callers
on the `SessionStore` methods so the swap stays local to this module.
"""

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.schemas import SessionStatus, Sentiment


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class StoredMessage:
    role: str  # "client" | "ai"
    text: str
    at: datetime
    sentiment: Sentiment | None = None
    intensity: int | None = None


@dataclass
class Session:
    id: str
    created_at: datetime
    updated_at: datetime
    status: SessionStatus = SessionStatus.ai
    sentiment: Sentiment = Sentiment.neutral
    intensity: int = 1
    peak_intensity: int = 1
    flagged_at: datetime | None = None
    taken_over_at: datetime | None = None
    messages: list[StoredMessage] = field(default_factory=list)

    @property
    def ai_paused(self) -> bool:
        return self.status == SessionStatus.counselor


# Dashboard order: needs a human first, then live counselor sessions, then autopilot.
_STATUS_RANK = {SessionStatus.flagged: 0, SessionStatus.counselor: 1, SessionStatus.ai: 2}


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str) -> Session:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                now = _now()
                session = Session(id=session_id, created_at=now, updated_at=now)
                self._sessions[session_id] = session
            return session

    def add_client_message(self, session: Session, text: str) -> None:
        now = _now()
        with self._lock:
            session.messages.append(StoredMessage("client", text, now))
            session.updated_at = now

    def record_ai_reply(
        self,
        session: Session,
        text: str,
        sentiment: Sentiment,
        intensity: int,
        takeover: bool,
    ) -> None:
        now = _now()
        with self._lock:
            session.messages.append(StoredMessage("ai", text, now, sentiment, intensity))
            session.sentiment = sentiment
            session.intensity = intensity
            session.peak_intensity = max(session.peak_intensity, intensity)
            session.updated_at = now
            # Flags are sticky: a calmer later message never unflags a session.
            if takeover and session.status == SessionStatus.ai:
                session.status = SessionStatus.flagged
                session.flagged_at = now

    def flag(self, session: Session) -> None:
        """Flag without an AI reply (crisis language while the AI is paused)."""
        with self._lock:
            if session.flagged_at is None:
                session.flagged_at = _now()

    def take_over(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None and session.status != SessionStatus.counselor:
                session.status = SessionStatus.counselor
                session.taken_over_at = _now()
            return session

    def release(self, session_id: str) -> Session | None:
        """Hand a session back to the AI. Stays flagged if it ever was."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None and session.status == SessionStatus.counselor:
                session.status = SessionStatus.flagged if session.flagged_at else SessionStatus.ai
                session.taken_over_at = None
            return session

    def list(self) -> list[Session]:
        sessions = list(self._sessions.values())
        # Newest activity first within each status group (stable sort).
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        sessions.sort(key=lambda s: _STATUS_RANK[s.status])
        return sessions


_store = SessionStore()


def get_session_store() -> SessionStore:
    """FastAPI dependency. Tests replace it via `app.dependency_overrides`."""
    return _store
