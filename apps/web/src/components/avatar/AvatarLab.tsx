"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { ChatMessageResponse, Sentiment, sendChatMessage } from "@/lib/api";
import {
  ANIMATION_TRIGGERS,
  PARAM_IDS,
  PARAM_RANGES,
  SENTIMENTS,
  type AvatarParams,
  type AvatarState,
  type ParamId,
} from "@/lib/avatar";
import Avatar from "./Avatar";
import styles from "./AvatarLab.module.css";

const TOUR_STEP_MS = 3000;

/** Debug page for exercising every expression, motion and param by hand. */
export default function AvatarLab() {
  const [state, setState] = useState<AvatarState>({
    sentiment: "neutral",
    intensity: 5,
    speaking: false,
  });
  const [locked, setLocked] = useState<Partial<AvatarParams>>({});
  const [touring, setTouring] = useState(false);
  const [draft, setDraft] = useState("");
  const [reply, setReply] = useState<ChatMessageResponse | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const readout = useRef<HTMLPreElement>(null);
  const lastReadout = useRef(0);

  const playMotion = (motion: string) =>
    setState((s) => ({ ...s, motion, motionKey: (s.motionKey ?? 0) + 1 }));

  // Tour: step through every sentiment, then every motion.
  useEffect(() => {
    if (!touring) return;
    const steps: Array<Partial<AvatarState>> = [
      ...SENTIMENTS.map((sentiment) => ({ sentiment, intensity: 8 })),
      ...ANIMATION_TRIGGERS.map((motion) => ({ sentiment: "neutral" as Sentiment, motion })),
      { speaking: true },
      { speaking: false },
    ];
    let i = 0;
    const step = () => {
      const next = steps[i++];
      if (!next) return setTouring(false);
      setState((s) => ({ ...s, ...next, motionKey: (s.motionKey ?? 0) + 1 }));
    };
    step();
    const id = setInterval(step, TOUR_STEP_MS);
    return () => clearInterval(id);
  }, [touring]);

  function handleFrame(params: AvatarParams, activeMotion: string | null) {
    const now = performance.now();
    if (!readout.current || now - lastReadout.current < 100) return;
    lastReadout.current = now;
    readout.current.textContent =
      `motion: ${activeMotion ?? "—"}\n` +
      PARAM_IDS.map((id) => `${id.padEnd(16)} ${params[id].toFixed(2)}`).join("\n");
  }

  function toggleLock(id: ParamId, on: boolean) {
    setLocked((prev) => {
      const next = { ...prev };
      if (on) next[id] = PARAM_RANGES[id][0] + (PARAM_RANGES[id][1] - PARAM_RANGES[id][0]) / 2;
      else delete next[id];
      return next;
    });
  }

  async function handleSend(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!draft.trim()) return;
    setApiError(null);
    try {
      const r = await sendChatMessage({ message: draft.trim() });
      setReply(r);
      setState((s) => ({
        ...s,
        sentiment: r.sentiment,
        intensity: r.intensity,
        motion: r.animation_trigger,
        motionKey: (s.motionKey ?? 0) + 1,
      }));
    } catch {
      setApiError("Couldn't reach the API.");
    }
  }

  return (
    <main className={styles.lab}>
      <section className={styles.viewport}>
        <Avatar state={{ ...state, paramOverrides: locked }} onFrame={handleFrame} />
        <pre ref={readout} className={styles.readout} aria-label="Live parameters" />
      </section>

      <section className={styles.controls}>
        <h1>Avatar lab</h1>

        <fieldset>
          <legend>Sentiment</legend>
          <div className={styles.row}>
            {SENTIMENTS.map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={state.sentiment === s}
                onClick={() => setState((prev) => ({ ...prev, sentiment: s }))}
              >
                {s}
              </button>
            ))}
          </div>
          <label className={styles.slider}>
            Intensity {state.intensity}
            <input
              type="range"
              min={1}
              max={10}
              value={state.intensity}
              onChange={(e) => setState((s) => ({ ...s, intensity: Number(e.target.value) }))}
            />
          </label>
        </fieldset>

        <fieldset>
          <legend>Animation trigger</legend>
          <div className={styles.row}>
            {ANIMATION_TRIGGERS.map((m) => (
              <button key={m} type="button" onClick={() => playMotion(m)}>
                {m}
              </button>
            ))}
          </div>
          <label>
            <input
              type="checkbox"
              checked={state.speaking}
              onChange={(e) => setState((s) => ({ ...s, speaking: e.target.checked }))}
            />{" "}
            Speaking (lip flap)
          </label>
          <button type="button" onClick={() => setTouring((t) => !t)}>
            {touring ? "Stop tour" : "Play tour of everything"}
          </button>
        </fieldset>

        <fieldset>
          <legend>Send through the API</legend>
          <form className={styles.row} onSubmit={handleSend}>
            <label htmlFor="lab-input" className={styles.srOnly}>
              Test message
            </label>
            <input
              id="lab-input"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="e.g. I feel hopeless"
            />
            <button type="submit">Send</button>
          </form>
          {apiError && <p role="status">{apiError}</p>}
          {reply && (
            <p className={styles.reply}>
              {reply.text_response}
              <br />
              <small>
                {reply.sentiment} · {reply.intensity}/10 · {reply.animation_trigger}
                {reply.human_takeover_flag && " · TAKEOVER"}
              </small>
            </p>
          )}
        </fieldset>

        <fieldset>
          <legend>Lock parameters (simulates counselor face tracking)</legend>
          {PARAM_IDS.map((id) => {
            const [min, max] = PARAM_RANGES[id];
            const value = locked[id];
            return (
              <div key={id} className={styles.param}>
                <label>
                  <input
                    type="checkbox"
                    checked={value !== undefined}
                    onChange={(e) => toggleLock(id, e.target.checked)}
                  />{" "}
                  {id}
                </label>
                <input
                  type="range"
                  aria-label={`${id} value`}
                  min={min}
                  max={max}
                  step={(max - min) / 100}
                  disabled={value === undefined}
                  value={value ?? (min + max) / 2}
                  onChange={(e) => setLocked((prev) => ({ ...prev, [id]: Number(e.target.value) }))}
                />
              </div>
            );
          })}
        </fieldset>
      </section>
    </main>
  );
}
