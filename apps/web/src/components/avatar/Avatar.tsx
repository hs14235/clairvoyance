"use client";

import { useEffect, useRef } from "react";

import { AvatarDriver, type AvatarParams, type AvatarState } from "@/lib/avatar";
import type { AvatarRenderer } from "./renderer";
import SvgFace from "./SvgFace";
import styles from "./Avatar.module.css";

interface Props {
  state: AvatarState;
  /** Called every frame with the params drawn, e.g. for a debug readout. */
  onFrame?: (params: AvatarParams, activeMotion: string | null) => void;
  className?: string;
}

export default function Avatar({ state, onFrame, className }: Props) {
  const driver = useRef<AvatarDriver | null>(null);
  driver.current ??= new AvatarDriver();
  const renderer = useRef<AvatarRenderer>(null);
  const onFrameRef = useRef(onFrame);

  useEffect(() => {
    onFrameRef.current = onFrame;
  }, [onFrame]);

  useEffect(() => {
    driver.current!.setState(state);
  }, [state]);

  useEffect(() => {
    const d = driver.current!;
    const media = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const applyMotionPref = () => d.setOptions({ reducedMotion: !!media?.matches });
    applyMotionPref();
    media?.addEventListener?.("change", applyMotionPref);

    const frame = (dt: number) => {
      const params = d.tick(dt);
      renderer.current?.render(params);
      onFrameRef.current?.(params, d.activeMotion);
    };

    let raf = 0;
    if (typeof requestAnimationFrame === "function") {
      let last = performance.now();
      const loop = (now: number) => {
        frame(Math.min(now - last, 50)); // cap dt so a background tab doesn't jump
        last = now;
        raf = requestAnimationFrame(loop);
      };
      raf = requestAnimationFrame(loop);
    } else {
      frame(16);
    }
    return () => {
      cancelAnimationFrame?.(raf);
      media?.removeEventListener?.("change", applyMotionPref);
    };
  }, []);

  return (
    <div
      className={`${styles.avatar} ${className ?? ""}`}
      role="img"
      aria-label={`Avatar, ${state.sentiment} expression${state.speaking ? ", speaking" : ""}`}
      data-sentiment={state.sentiment}
      data-intensity={state.intensity}
      data-motion={state.motion ?? "idle_listen"}
      data-speaking={state.speaking || undefined}
    >
      <SvgFace ref={renderer} />
    </div>
  );
}
