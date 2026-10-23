from fastapi import FastAPI

from src.routers import chat

app = FastAPI(title="Clairvoyance API", version="0.1.0")
app.include_router(chat.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
