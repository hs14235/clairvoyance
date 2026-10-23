# Run the full voice loop locally (Windows)

Mic → `POST /api/v1/speech/transcribe` (faster-whisper) → `POST /api/v1/chat/message`
(Qwen via Ollama, then triage rules) → reply bubble, avatar, optional spoken reply.

Everything runs on your machine. No paid API, no data leaves the laptop.

## Quick start

You need Python 3.11+ (`winget install --id Python.Python.3.12`), Node 20.9+, and Ollama:

```powershell
winget install --id Ollama.Ollama      # then open a NEW terminal
.\scripts\start-api.ps1                # terminal 1: checks everything, then runs the API
.\scripts\smoke-test.ps1               # terminal 2: speech -> Whisper -> Qwen, with timings
cd apps/web; npm install; npm run dev  # terminal 2: web app on http://localhost:3000
```

`start-api.ps1` checks Python, installs packages, starts Ollama if it isn't
running, pulls the model if it's missing, loads it into memory, and starts the
API. Any failure stops with a red line saying what to do.

`smoke-test.ps1` makes Windows speak a sentence into a WAV file, sends it
through Whisper and Qwen, and prints what was heard, Qwen's reply, and how long
each step took. Run it before opening the browser so you know the backend works.
Try `-Sentence "I feel hopeless and I can't go on"` to see a takeover.

If PowerShell blocks the scripts: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Which Qwen model

The script picks **`qwen2.5:7b`** when the machine has 16 GB+ RAM and
**`qwen2.5:1.5b`** otherwise. Override with `-Model`.

| Tag | Download | Licence | Notes |
|---|---|---|---|
| `qwen2.5:1.5b` | ~1 GB | Apache 2.0 | Fast on any CPU. Replies are simpler; ratings are rougher |
| `qwen2.5:3b` | ~1.9 GB | Qwen Research (non-commercial) | Middle ground; fine for a personal demo |
| `qwen2.5:7b` | ~4.7 GB | Apache 2.0 | Noticeably better replies. On CPU expect several seconds per reply |

The reply format is enforced with a JSON schema (Ollama's structured outputs),
so even 1.5B can only produce valid sentiments, intensities and gestures. The
API also sends the last 8 messages so Qwen remembers the conversation.

## Speech-to-text

Whisper `small` on CPU (int8) by default, English only (`-Language auto` to
detect). The API starts loading it in the background at startup; the first run
downloads ~0.5 GB from huggingface.co. `-WhisperModel base` is faster and less
accurate; `medium` is slower and better.

In the browser: tap 🎤, speak, tap ■ (recording stops by itself after 60 s).
Tick **Speak replies aloud** to hear replies; the avatar's mouth follows the
real speech. On Edge, the "Natural" voices sound best. The mic only works on
`localhost` or HTTPS.

## Is it working? `GET /api/v1/status`

http://localhost:8000/api/v1/status reports both backends:

```json
{"llm": {"provider": "openai", "ok": true, "detail": "qwen2.5:7b at http://127.0.0.1:11434/v1"},
 "stt": {"provider": "faster-whisper", "ok": true, "detail": "Whisper small loaded (cpu, int8)"}}
```

If Qwen can't be used for a reply, the chat still answers with a canned line,
the bubble says **Offline reply**, and the API terminal logs the reason. If the
message had crisis language, the canned line is a crisis-safe one and the
takeover still fires.

## Troubleshooting

| You see | Fix |
|---|---|
| `Can't reach http://127.0.0.1:11434/v1. Is Ollama running?` | Open the Ollama app from the Start menu, or run `ollama serve` |
| `Model 'qwen2.5:7b' isn't pulled. Run: ollama pull qwen2.5:7b` | Run that command (the script does it for you) |
| `The model took longer than 120s` | First reply after a cold start loads the model. Retry, use a smaller model, or set `$env:LLM_TIMEOUT_SECONDS = "300"` |
| `Speech-to-text isn't ready yet: Couldn't load Whisper...` | The download failed. Check your internet, then send another voice message (it retries) |
| Transcripts in the wrong language | Keep the default `-Language en` |
| `pip` fails building `av` | Python is older than 3.11. Install 3.12 and delete `apps/api/.venv` |
| Hugging Face prints a "symlinks" warning | Harmless on Windows; the model still caches |
| Mic button missing | Browser can't record, or the page isn't on `localhost`/HTTPS |

## Docker alternative

`docker compose up --build` runs Ollama and the API (with faster-whisper) in
containers; then run `docker compose exec ollama ollama pull qwen2.5:1.5b`
once. Run the web app with `npm run dev` as above. On Windows, Docker runs
Ollama on CPU unless GPU passthrough is set up, so the native install above is
usually faster.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `stub` | `stub` (keyword stand-in) or `openai` (any OpenAI-compatible server) |
| `LLM_BASE_URL` | `http://127.0.0.1:11434/v1` | Ollama's OpenAI-compatible endpoint |
| `LLM_MODEL` | `qwen2.5:1.5b` | Model name on that server (`start-api.ps1` may pick 7b) |
| `LLM_API_KEY` | none | Sent as `Bearer` token; Ollama ignores it |
| `LLM_TIMEOUT_SECONDS` | `120` | Per-request timeout |
| `LLM_JSON_MODE` | `schema` | `schema` (JSON schema), `object` (JSON mode), `none`. A 400 on `schema` drops to `object` automatically |
| `STT_PROVIDER` | `stub` | `stub` (fixed phrase) or `faster-whisper` |
| `STT_MODEL` | `small` | Whisper size: `base`, `small`, `medium`, ... |
| `STT_DEVICE` / `STT_COMPUTE_TYPE` | `cpu` / `int8` | `cuda` / `float16` on an NVIDIA GPU with CUDA 12 + cuDNN 9 |
| `STT_LANGUAGE` | `en` | `auto` to detect |
| `STT_BEAM_SIZE` | `5` | `1` is faster, slightly less accurate |

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
