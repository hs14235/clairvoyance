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
    throw new Error(`API returned ${res.status}`);
  }
  return res.json();
}
