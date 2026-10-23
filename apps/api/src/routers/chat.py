from fastapi import APIRouter, Depends

from src.schemas import ChatMessageRequest, ChatMessageResponse
from src.services.qwen_service import LLMClient, get_llm_client
from src.utils import triage_rules

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse)
async def post_message(
    body: ChatMessageRequest,
    llm: LLMClient = Depends(get_llm_client),
) -> ChatMessageResponse:
    analysis = await llm.analyze(body.message)
    sentiment, intensity, takeover = triage_rules.evaluate(body.message, analysis)
    return ChatMessageResponse(
        text_response=analysis.text_response,
        sentiment=sentiment,
        intensity=intensity,
        animation_trigger=analysis.animation_trigger,
        human_takeover_flag=takeover,
    )
