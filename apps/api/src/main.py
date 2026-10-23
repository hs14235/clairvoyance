import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import chat, sessions, speech, status
from src.services.speech_service import STTUnavailable, get_transcriber

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Comma-separated list of browser origins allowed to call the API.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]



@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load Whisper in the background so the first voice message isn't the one
    # that waits for the download. The API is usable meanwhile.
    stt = get_transcriber()
    task = None
    if hasattr(stt, "load"):

        async def preload() -> None:
            try:
                await asyncio.to_thread(stt.load)
            except STTUnavailable:
                pass  # already logged; /api/v1/status and /transcribe report it

        task = asyncio.create_task(preload())
    yield
    if task:
        task.cancel()


app = FastAPI(title="Clairvoyance API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(chat.router)
app.include_router(speech.router)
app.include_router(sessions.router)
app.include_router(status.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
