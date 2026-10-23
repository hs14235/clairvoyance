"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { ChatMessageResponse, sendChatMessage } from "@/lib/api";
import styles from "./Chat.module.css";

type Entry =
  | { id: number; role: "user"; text: string }
  | { id: number; role: "assistant"; reply: ChatMessageResponse };

export default function Chat() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Once any reply flags takeover, the whole session stays flagged.
  const [takeover, setTakeover] = useState(false);
  const sessionId = useRef<string | null>(null);
  const nextId = useRef(0);
  const logEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEnd.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [entries, pending]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const message = draft.trim();
    if (!message || pending) return;

    sessionId.current ??= crypto.randomUUID();
    setEntries((prev) => [
      ...prev,
      { id: nextId.current++, role: "user", text: message },
    ]);
    setDraft("");
    setError(null);
    setPending(true);

    try {
      const reply = await sendChatMessage({
        message,
        session_id: sessionId.current,
      });
      setEntries((prev) => [
        ...prev,
        { id: nextId.current++, role: "assistant", reply },
      ]);
      if (reply.human_takeover_flag) setTakeover(true);
    } catch {
      setError("Couldn't reach the server. Is the API running on port 8000?");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className={styles.chat}>
      {takeover && (
        <div role="alert" className={styles.takeover}>
          <strong>A counselor has been notified and will join shortly.</strong>
          <span>
            If you are in immediate danger, call or text 988 (US) or your local
            emergency number.
          </span>
        </div>
      )}

      <div className={styles.log} aria-live="polite">
        {entries.length === 0 && (
          <p className={styles.empty}>
            Hi, I&apos;m here to listen. How are you feeling today?
          </p>
        )}
        {entries.map((entry) =>
          entry.role === "user" ? (
            <div key={entry.id} className={`${styles.bubble} ${styles.user}`}>
              {entry.text}
            </div>
          ) : (
            <div
              key={entry.id}
              className={`${styles.bubble} ${styles.assistant}`}
            >
              <p>{entry.reply.text_response}</p>
              <div className={styles.meta}>
                <span className={styles.badge} data-sentiment={entry.reply.sentiment}>
                  {entry.reply.sentiment}
                </span>
                <span
                  className={styles.intensity}
                  aria-label={`Intensity ${entry.reply.intensity} of 10`}
                >
                  intensity {entry.reply.intensity}/10
                  <span className={styles.bar}>
                    <span
                      className={styles.fill}
                      style={{ width: `${entry.reply.intensity * 10}%` }}
                      data-high={entry.reply.intensity >= 8 || undefined}
                    />
                  </span>
                </span>
              </div>
            </div>
          ),
        )}
        {pending && <p className={styles.typing}>Typing…</p>}
        <div ref={logEnd} />
      </div>

      {error && (
        <p className={styles.error} role="status">
          {error}
        </p>
      )}

      <form className={styles.composer} onSubmit={handleSubmit}>
        <label htmlFor="chat-input" className={styles.srOnly}>
          Message
        </label>
        <input
          id="chat-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Type how you're feeling…"
          maxLength={4000}
          autoComplete="off"
        />
        <button type="submit" disabled={pending || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}
