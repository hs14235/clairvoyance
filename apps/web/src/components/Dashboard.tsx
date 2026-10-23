"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  SessionDetail,
  SessionStatus,
  SessionSummary,
  getSession,
  listSessions,
  releaseSession,
  takeOverSession,
} from "@/lib/sessions";
import styles from "./Dashboard.module.css";

// Polling until the API has a push channel (WebSockets) for the dashboard.
export const POLL_MS = 3000;

const STATUS_LABEL: Record<SessionStatus, string> = {
  flagged: "Needs counselor",
  counselor: "Counselor live",
  ai: "AI",
};

function timeAgo(iso: string, now: number): string {
  const seconds = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.round(minutes / 60)}h ago`;
}

export default function Dashboard() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Set from the poll, not at render: Date.now() is not allowed during prerender.
  const [now, setNow] = useState(0);
  // Latest selection, so a slow poll can't overwrite a newer click.
  const selectedRef = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await listSessions();
      setSessions(list);
      setError(null);
      setNow(Date.now());
      if (selectedId) {
        const fetched = await getSession(selectedId);
        if (selectedRef.current === fetched.id) setDetail(fetched);
      }
    } catch {
      setError("Couldn't reach the API. Is it running on port 8000?");
    }
  }, [selectedId]);

  useEffect(() => {
    // refresh only sets state after awaiting the API, so this doesn't cascade renders.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  async function toggleTakeover(session: SessionDetail) {
    setBusy(true);
    try {
      const updated =
        session.status === "counselor"
          ? await releaseSession(session.id)
          : await takeOverSession(session.id);
      if (selectedRef.current === updated.id) setDetail(updated);
      setSessions(await listSessions());
    } catch {
      setError("Takeover request failed. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const flaggedCount = sessions.filter((s) => s.status === "flagged").length;

  return (
    <div className={styles.dashboard}>
      <section className={styles.list} aria-label="Sessions">
        <p className={styles.summary}>
          {sessions.length} active · {flaggedCount} need a counselor
        </p>
        {error && (
          <p className={styles.error} role="status">
            {error}
          </p>
        )}
        {sessions.length === 0 && !error && (
          <p className={styles.empty}>No sessions yet. Open the chat page to start one.</p>
        )}
        <ul>
          {sessions.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                className={styles.row}
                data-status={s.status}
                aria-current={s.id === selectedId || undefined}
                onClick={() => {
                  selectedRef.current = s.id;
                  setSelectedId(s.id);
                  setDetail(null);
                }}
              >
                <span className={styles.rowTop}>
                  <span className={styles.status} data-status={s.status}>
                    {STATUS_LABEL[s.status]}
                  </span>
                  <span className={styles.metric}>
                    {s.sentiment} · {s.intensity}/10
                    {s.peak_intensity > s.intensity && ` (peak ${s.peak_intensity})`}
                  </span>
                  <span className={styles.time}>{timeAgo(s.updated_at, now)}</span>
                </span>
                <span className={styles.preview}>{s.last_client_message ?? "…"}</span>
                <span className={styles.sessionId}>{s.id.slice(0, 8)}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.detail} aria-label="Session detail">
        {!selectedId && <p className={styles.empty}>Select a session to read it.</p>}
        {selectedId && !detail && <p className={styles.empty}>Loading…</p>}
        {detail && (
          <>
            <header className={styles.detailHeader}>
              <div>
                <span className={styles.status} data-status={detail.status}>
                  {STATUS_LABEL[detail.status]}
                </span>{" "}
                <span className={styles.metric}>
                  {detail.sentiment} · intensity {detail.intensity}/10 · peak{" "}
                  {detail.peak_intensity}/10
                </span>
              </div>
              <button
                type="button"
                className={styles.takeover}
                data-active={detail.status === "counselor" || undefined}
                disabled={busy}
                onClick={() => toggleTakeover(detail)}
              >
                {detail.status === "counselor" ? "Hand back to AI" : "Take over"}
              </button>
            </header>
            <ol className={styles.transcript}>
              {detail.messages.map((m, i) => (
                <li key={i} className={styles.message} data-role={m.role}>
                  <span className={styles.who}>{m.role === "client" ? "Client" : "AI"}</span>
                  <p>{m.text}</p>
                  {m.intensity !== null && (
                    <span className={styles.metric}>
                      {m.sentiment} · {m.intensity}/10
                    </span>
                  )}
                </li>
              ))}
            </ol>
          </>
        )}
      </section>
    </div>
  );
}
