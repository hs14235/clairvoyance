// Counselor dashboard client. Mirrors the session models in apps/api/src/schemas.py.

import { API_URL, Sentiment } from "./api";

export type SessionStatus = "ai" | "flagged" | "counselor";

export interface SessionSummary {
  id: string;
  status: SessionStatus;
  sentiment: Sentiment;
  intensity: number;
  peak_intensity: number;
  message_count: number;
  last_client_message: string | null;
  created_at: string;
  updated_at: string;
  flagged_at: string | null;
  taken_over_at: string | null;
}

export interface SessionMessage {
  role: "client" | "ai";
  text: string;
  at: string;
  sentiment: Sentiment | null;
  intensity: number | null;
}

export interface SessionDetail extends SessionSummary {
  messages: SessionMessage[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}/api/v1/sessions${path}`, init);
  if (!res.ok) {
    throw new Error(`API returned ${res.status}`);
  }
  return res.json();
}

export function listSessions(signal?: AbortSignal): Promise<SessionSummary[]> {
  return request("", { signal });
}

export function getSession(id: string, signal?: AbortSignal): Promise<SessionDetail> {
  return request(`/${encodeURIComponent(id)}`, { signal });
}

export function takeOverSession(id: string): Promise<SessionDetail> {
  return request(`/${encodeURIComponent(id)}/takeover`, { method: "POST" });
}

export function releaseSession(id: string): Promise<SessionDetail> {
  return request(`/${encodeURIComponent(id)}/release`, { method: "POST" });
}
