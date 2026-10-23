import uuid

from fastapi import APIRouter, Depends

from src.schemas import ChatMessageRequest, ChatMessageResponse
from src.services.qwen_service import LLMClient, Turn, get_llm_client
from src.services.session_store import SessionStore, get_session_store
from src.utils import triage_rules

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

COUNSELOR_HOLDING_REPLY = "A counselor is with you now and will reply here shortly."
# Used instead of the generic fallback when the model is down but triage escalated.
CRISIS_FALLBACK_REPLY = (
    "Thank you for telling me. I'm bringing in a counselor to be with you right now, "
    "and you don't have to go through this alone. Please stay with me."
)


@router.post("/message", response_model=ChatMessageResponse)
async def post_message(
    body: ChatMessageRequest,
    llm: LLMClient = Depends(get_llm_client),
    store: SessionStore = Depends(get_session_store),
) -> ChatMessageResponse:
    session = store.get_or_create(body.session_id or str(uuid.uuid4()))
    store.add_client_message(session, body.message)

    # Counselor has the session: no model call, just log and keep crisis checks.
    if session.ai_paused:
        if triage_rules.contains_crisis_language(body.message):
            store.flag(session)
        return ChatMessageResponse(
            text_response=COUNSELOR_HOLDING_REPLY,
            sentiment=session.sentiment,
            intensity=session.intensity,
            animation_trigger="idle_listen",
            human_takeover_flag=True,
            session_id=session.id,
            ai_paused=True,
        )

    # Earlier turns give the model context; the message just added is sent separately.
    history = [
        Turn("user" if m.role == "client" else "assistant", m.text) for m in session.messages[:-1]
    ]
    analysis = await llm.analyze(body.message, history)
    sentiment, intensity, takeover = triage_rules.evaluate(body.message, analysis)
    text, trigger = analysis.text_response, analysis.animation_trigger
    if analysis.fallback_reason and takeover:
        text, trigger = CRISIS_FALLBACK_REPLY, "concerned_lean_in"
    store.record_ai_reply(session, text, sentiment, intensity, takeover)
    return ChatMessageResponse(
        text_response=text,
        sentiment=sentiment,
        intensity=intensity,
        animation_trigger=trigger,
        human_takeover_flag=takeover,
        session_id=session.id,
        model_fallback=analysis.fallback_reason is not None,
    )
