import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import chat, speech

# Comma-separated list of browser origins allowed to call the API.
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app = FastAPI(title="Clairvoyance API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(chat.router)
app.include_router(speech.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
