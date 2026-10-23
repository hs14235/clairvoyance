"use client";

import { useEffect, useRef, useState } from "react";

import { transcribeAudio } from "@/lib/api";
import { useBrowserSupport } from "@/lib/useBrowserSupport";
import styles from "./Chat.module.css";

type MicState = "idle" | "recording" | "transcribing";

// Preferred first. Chrome/Firefox/Edge record webm/opus; Safari records mp4/aac.
const MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return MIME_TYPES.find((t) => MediaRecorder.isTypeSupported?.(t));
}

export function micSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined"
  );
}

interface Props {
  disabled?: boolean;
  onTranscript: (text: string) => void;
  onError: (message: string) => void;
}

/** Tap to start recording, tap again to stop and transcribe. */
export default function MicButton({ disabled, onTranscript, onError }: Props) {
  const [state, setState] = useState<MicState>("idle");
  const supported = useBrowserSupport(micSupported);
  const recorder = useRef<MediaRecorder | null>(null);

  useEffect(
    () => () => recorder.current?.stream.getTracks().forEach((t) => t.stop()),
    [],
  );

  async function start() {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError("Microphone access was blocked. Allow it in the browser's site settings.");
      return;
    }
    const mimeType = pickMimeType();
    const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      recorder.current = null;
      const audio = new Blob(chunks, { type: rec.mimeType || mimeType || "audio/webm" });
      if (audio.size === 0) {
        setState("idle");
        return;
      }
      setState("transcribing");
      try {
        const { text } = await transcribeAudio(audio);
        if (text.trim()) onTranscript(text.trim());
        else onError("I didn't catch that. Try again a little closer to the mic.");
      } catch {
        onError("Couldn't transcribe the recording. Is the API running on port 8000?");
      } finally {
        setState("idle");
      }
    };
    recorder.current = rec;
    rec.start();
    setState("recording");
  }

  function stop() {
    recorder.current?.stop();
  }

  if (!supported) return null;

  const label =
    state === "recording" ? "Stop recording" : state === "transcribing" ? "Transcribing" : "Record voice message";

  return (
    <button
      type="button"
      className={styles.mic}
      data-state={state}
      aria-label={label}
      aria-pressed={state === "recording"}
      title={label}
      disabled={disabled || state === "transcribing"}
      onClick={state === "recording" ? stop : start}
    >
      {state === "recording" ? "■" : state === "transcribing" ? "…" : "🎤"}
    </button>
  );
}
