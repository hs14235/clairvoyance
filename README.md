# Clairvoyance

AI-assisted mental-health intake and triage. A Live2D avatar handles baseline
intake; a student counselor takes over high-priority sessions live.

## Layout

| Path | What |
|---|---|
| `apps/api` | FastAPI backend (chat + triage) |
| `apps/web` | Next.js client: chat page today, counselor dashboard later ([README](apps/web/README.md)) |
| `apps/mobile` | Expo client (not started) |
| `packages` | Shared TS code (not started) |

## Backend quickstart

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest tests/test_triage_pipeline.py
uvicorn src.main:app --reload   # docs at http://localhost:8000/docs
```

Set `CORS_ORIGINS` (comma-separated) to change which browser origins may call
the API; it defaults to `http://localhost:3000` for the web app.

Or with Docker: `docker build -t clairvoyance-api apps/api && docker run -p 8000:8000 clairvoyance-api`.

```bash
curl -X POST localhost:8000/api/v1/chat/message \
  -H 'content-type: application/json' -d '{"message": "I feel hopeless"}'
# {"text_response":"...","sentiment":"distressed","intensity":9,
#  "animation_trigger":"concerned_lean_in","human_takeover_flag":true}
```

## Web quickstart

See [apps/web/README.md](apps/web/README.md) (PowerShell commands included).

![Chat page](docs/web-chat.png)

## How triage works

1. `services/qwen_service.py` defines an `LLMClient` interface. Today only a
   deterministic keyword stub implements it (`LLM_PROVIDER=stub`, the default).
2. `utils/triage_rules.py` validates the model output (clamps intensity to 1-10,
   maps unknown sentiments to `neutral`) and decides `human_takeover_flag`:
   true when intensity >= 8 **or** the message contains crisis language. The
   model never sets the flag itself.

> The stub and keyword list are placeholders, not clinically validated.
