"""Counselor dashboard endpoints.

No auth yet: anyone who can reach the API can read transcripts and take over
sessions. Must be locked to counselor accounts before any real client data.
"""

from fastapi import APIRouter, Depends, HTTPException

from src.schemas import MessageOut, SessionDetail, SessionSummary
from src.services.session_store import Session, SessionStore, get_session_store

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def _summary_fields(session: Session) -> dict:
    return {
        "id": session.id,
        "status": session.status,
        "sentiment": session.sentiment,
        "intensity": session.intensity,
        "peak_intensity": session.peak_intensity,
        "message_count": len(session.messages),
        "last_client_message": next(
            (m.text for m in reversed(session.messages) if m.role == "client"), None
        ),
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "flagged_at": session.flagged_at,
        "taken_over_at": session.taken_over_at,
    }


def _detail(session: Session) -> SessionDetail:
    return SessionDetail(
        **_summary_fields(session),
        messages=[
            MessageOut(role=m.role, text=m.text, at=m.at, sentiment=m.sentiment, intensity=m.intensity)
            for m in session.messages
        ],
    )


def _require(session: Session | None) -> Session:
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("", response_model=list[SessionSummary])
async def list_sessions(store: SessionStore = Depends(get_session_store)) -> list[SessionSummary]:
    """Flagged sessions first, then counselor-held, then AI; newest activity first in each."""
    return [SessionSummary(**_summary_fields(s)) for s in store.list()]


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, store: SessionStore = Depends(get_session_store)) -> SessionDetail:
    return _detail(_require(store.get(session_id)))


@router.post("/{session_id}/takeover", response_model=SessionDetail)
async def take_over(session_id: str, store: SessionStore = Depends(get_session_store)) -> SessionDetail:
    """Pause the AI for this session. Idempotent."""
    return _detail(_require(store.take_over(session_id)))


@router.post("/{session_id}/release", response_model=SessionDetail)
async def release(session_id: str, store: SessionStore = Depends(get_session_store)) -> SessionDetail:
    """Hand the session back to the AI. Idempotent."""
    return _detail(_require(store.release(session_id)))
