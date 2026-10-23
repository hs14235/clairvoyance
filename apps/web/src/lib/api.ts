// Mirrors apps/api/src/schemas.py. Keep the two in sync.

export type Sentiment =
  | "calm"
  | "neutral"
  | "sad"
  | "anxious"
  | "angry"
  | "distressed";

export interface ChatMessageRequest {
  message: string;
  session_id?: string | null;
}

export interface ChatMessageResponse {
  text_response: string;
  sentiment: Sentiment;
  intensity: number;
  animation_trigger: string;
  human_takeover_flag: boolean;
  // Optional here so existing fixtures stay valid; the API always sends them.
  session_id?: string;
  ai_paused?: boolean;
  // True when the model was unavailable and text_response is a canned line.
  model_fallback?: boolean;
}

/** Non-2xx response. `detail` is FastAPI's error message when it sent one. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail?: string,
  ) {
    super(detail ? `API returned ${status}: ${detail}` : `API returned ${status}`);
  }
}

async function errorFrom(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    return new ApiError(res.status, typeof body?.detail === "string" ? body.detail : undefined);
  } catch {
    return new ApiError(res.status);
  }
}

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function sendChatMessage(
  body: ChatMessageRequest,
  signal?: AbortSignal,
): Promise<ChatMessageResponse> {
  const res = await fetch(`${API_URL}/api/v1/chat/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) {
    throw await errorFrom(res);
  }
  return res.json();
}

export interface TranscriptionResponse {
  text: string;
}

export async function transcribeAudio(
  audio: Blob,
  signal?: AbortSignal,
): Promise<TranscriptionResponse> {
  const ext = audio.type.includes("mp4") ? "mp4" : audio.type.includes("ogg") ? "ogg" : "webm";
  const form = new FormData();
  form.append("audio", audio, `speech.${ext}`);
  // No Content-Type header: the browser sets the multipart boundary itself.
  const res = await fetch(`${API_URL}/api/v1/speech/transcribe`, {
    method: "POST",
    body: form,
    signal,
  });
  if (!res.ok) {
    throw await errorFrom(res);
  }
  return res.json();
}
