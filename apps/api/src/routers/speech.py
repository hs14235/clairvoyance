from fastapi import APIRouter, Depends, HTTPException, UploadFile

from src.schemas import TranscriptionResponse
from src.services.speech_service import Transcriber, get_transcriber

router = APIRouter(prefix="/api/v1/speech", tags=["speech"])

# ~60 s of opus audio is well under 1 MB; this just stops abuse.
MAX_AUDIO_BYTES = 10 * 1024 * 1024


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe(
    audio: UploadFile,
    stt: Transcriber = Depends(get_transcriber),
) -> TranscriptionResponse:
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if not data:
        raise HTTPException(status_code=422, detail="Empty audio upload")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio upload too large")
    return TranscriptionResponse(text=await stt.transcribe(data))
