# web

Next.js client for Clairvoyance. Today it is a single chat page that calls
`POST /api/v1/chat/message` and shows the reply, the sentiment, the intensity,
and a takeover banner when the API sets `human_takeover_flag`.

`/dashboard` is the counselor view: sessions with flagged ones first, the
transcript of the selected session, and a Take over / Hand back button. It polls
the API every 3 seconds. No login yet (see the root README's known gaps).

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

Open http://localhost:3000 for the chat and http://localhost:3000/dashboard for the counselor view.

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
| `src/app/dashboard/page.tsx` | Counselor dashboard route |
| `src/components/Dashboard.tsx` | Session list, transcript, takeover toggle (client component) |
| `src/lib/sessions.ts` | Typed client for `/api/v1/sessions` |
