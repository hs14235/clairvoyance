# web

Next.js client for Clairvoyance. Today it is a single chat page that calls
`POST /api/v1/chat/message` and shows the reply, the sentiment, the intensity,
and a takeover banner when the API sets `human_takeover_flag`. The Live2D
avatar and the counselor dashboard come later.

![Chat page](../../docs/web-chat.png)

## Run it locally (Windows PowerShell)

Start the API in one terminal:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
uvicorn src.main:app --reload
```

Start the web app in a second terminal (Node 20.9+):

```powershell
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000.

The API URL defaults to `http://localhost:8000`. To point elsewhere, copy
`.env.example` to `.env.local` and change `NEXT_PUBLIC_API_URL`. The API only
accepts browser calls from origins in its `CORS_ORIGINS` env var
(comma-separated, default `http://localhost:3000`).

## Checks

```powershell
npm run lint
npm run typecheck
npm test
npm run build
```

## Layout

| Path | What |
|---|---|
| `src/app/page.tsx` | Page shell |
| `src/components/Chat.tsx` | Chat UI and state (client component) |
| `src/components/Chat.test.tsx` | Vitest + Testing Library tests, `fetch` mocked |
| `src/lib/api.ts` | Typed client; types mirror `apps/api/src/schemas.py` |
