# Run the full voice loop locally (Windows)

Mic → `POST /api/v1/speech/transcribe` (faster-whisper) → `POST /api/v1/chat/message`
(Qwen via Ollama, then triage rules) → reply bubble, optional spoken reply.

Everything runs on your machine. No paid API, no data leaves the laptop.

## 1. Install Ollama and pull Qwen (one time)

```powershell
winget install --id Ollama.Ollama
# open a NEW terminal so `ollama` is on PATH; the server runs in the background
ollama pull qwen2.5:3b
curl.exe http://localhost:11434/v1/models   # should list qwen2.5:3b
```

Which Qwen 2.5 size (download sizes from the Ollama library):

| Tag | Download | Notes |
|---|---|---|
| `qwen2.5:1.5b` | ~1 GB | Fast on any laptop CPU, weaker JSON and tone |
| `qwen2.5:3b` | ~1.9 GB | **Default.** Good balance on 8-16 GB RAM |
| `qwen2.5:7b` | ~4.7 GB | Noticeably better replies; wants 16 GB RAM or a GPU |

> License: the 3B weights use the Qwen Research License (non-commercial);
> 1.5B and 7B are Apache 2.0. Fine for a demo; pick 7B or a hosted API before
> anything commercial.

## 2. Start the API

```powershell
.\scripts\start-api.ps1                     # Qwen 2.5 3B + Whisper small
.\scripts\start-api.ps1 -Model qwen2.5:7b   # bigger model
.\scripts\start-api.ps1 -Stub               # no models (same as CI / Pages demo)
```

The script creates `apps/api/.venv`, installs `requirements-voice.txt`, pulls the
model, sets the env vars below and runs uvicorn on http://localhost:8000. The
first voice message downloads the Whisper `small` model (roughly 0.5 GB) from
Hugging Face and takes a while; later ones are a few seconds on CPU.

If PowerShell blocks the script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## 3. Start the web app

```powershell
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000, tap 🎤, speak, tap ■. Tick **Speak replies aloud**
to hear the reply (browser speech synthesis, no server needed). The mic only
works on `localhost` or HTTPS; browsers block it on plain-HTTP LAN addresses.

## Docker alternative

`docker compose up --build` runs Ollama and the API (with faster-whisper) in
containers, then `docker compose exec ollama ollama pull qwen2.5:3b` once.
Run the web app with `npm run dev` as above. On Windows, Docker runs Ollama on
CPU unless GPU passthrough is set up, so the native install above is usually
faster.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `stub` | `stub` (keyword stand-in) or `openai` (any OpenAI-compatible server) |
| `LLM_BASE_URL` | `http://localhost:11434/v1` | Ollama's OpenAI-compatible endpoint |
| `LLM_MODEL` | `qwen2.5:3b` | Model name on that server |
| `LLM_API_KEY` | none | Sent as `Bearer` token; Ollama ignores it |
| `LLM_TIMEOUT_SECONDS` | `60` | Per-request timeout |
| `STT_PROVIDER` | `stub` | `stub` (fixed phrase) or `faster-whisper` |
| `STT_MODEL` | `small` | Whisper size: `base`, `small`, `medium`, ... |
| `STT_DEVICE` / `STT_COMPUTE_TYPE` | `cpu` / `int8` | `cuda` / `float16` on an NVIDIA GPU |
| `STT_LANGUAGE` | auto | e.g. `en` to skip language detection |

### Switching to a hosted Qwen API later

Alibaba Cloud Model Studio (DashScope) exposes an OpenAI-compatible endpoint,
so only env vars change:

```powershell
$env:LLM_PROVIDER = "openai"
$env:LLM_BASE_URL = "https://<your-workspace-endpoint>/compatible-mode/v1"
$env:LLM_API_KEY  = "<key>"
$env:LLM_MODEL    = "<model id from the Model Studio list>"
```

Check the current base URL and model ids in the Model Studio console; they
are region-specific.

## How failures behave

- Model down, slow, or returns non-JSON: the API logs a warning and replies
  with a neutral fallback line. Triage still runs on the user's text, so
  crisis keywords still trigger takeover.
- The model never sets `human_takeover_flag`; `utils/triage_rules.py` does.
