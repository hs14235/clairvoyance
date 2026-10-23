import os

from fastapi import APIRouter, Depends

from src.services.qwen_service import LLMClient, get_llm_client
from src.services.speech_service import Transcriber, get_transcriber

router = APIRouter(prefix="/api/v1", tags=["status"])


@router.get("/status")
async def status(
    llm: LLMClient = Depends(get_llm_client),
    stt: Transcriber = Depends(get_transcriber),
) -> dict:
    """Which model backends are configured and whether they work right now."""
    check = getattr(llm, "check", None)
    llm_status = await check() if check else {"ok": True, "detail": "stub (keyword rules)"}
    stt_status = stt.status() if hasattr(stt, "status") else {"ok": True, "detail": "custom"}
    return {
        "llm": {"provider": os.getenv("LLM_PROVIDER", "stub"), **llm_status},
        "stt": {"provider": os.getenv("STT_PROVIDER", "stub"), **stt_status},
    }
