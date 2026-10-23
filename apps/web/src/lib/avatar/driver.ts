import type { Sentiment } from "@/lib/api";
import { expressionFor } from "./expressions";
import { motionFor, type Motion } from "./motions";
import {
  NEUTRAL_PARAMS,
  PARAM_IDS,
  clampParams,
  type AvatarParams,
} from "./params";

/**
 * What drives the avatar. The chat (AI autopilot) sets sentiment, intensity,
 * motion and speaking; a counselor's face tracker (later) sets paramOverrides
 * every frame, which win over everything else for the params they name.
 */
export interface AvatarState {
  sentiment: Sentiment;
  intensity: number;
  /** An animation_trigger. Change `motionKey` to replay the same motion. */
  motion?: string;
  motionKey?: number;
  speaking: boolean;
  paramOverrides?: Partial<AvatarParams>;
}

export interface DriverOptions {
  /** Disables idle sway and gesture motion (prefers-reduced-motion). */
  reducedMotion?: boolean;
}

const EASE_PER_SECOND = 6; // how fast the face moves toward its target
const BLINK_MS = 140;

/**
 * Turns an AvatarState into per-frame AvatarParams: eases toward the
 * sentiment's expression, adds idle breathing and blinking, plays the current
 * motion, and flaps the mouth while speaking. Pure apart from its own state,
 * with time passed in, so it is unit-testable and renderer-agnostic.
 */
export class AvatarDriver {
  private current: AvatarParams = { ...NEUTRAL_PARAMS };
  private target: AvatarParams = { ...NEUTRAL_PARAMS };
  private state: AvatarState = { sentiment: "neutral", intensity: 1, speaking: false };
  private motion: Motion | null = null;
  private motionStart = 0;
  private nextBlink = 2500;
  private now = 0;

  constructor(private options: DriverOptions = {}) {}

  setOptions(options: DriverOptions) {
    this.options = options;
  }

  setState(next: AvatarState) {
    const prev = this.state;
    if (next.sentiment !== prev.sentiment || next.intensity !== prev.intensity) {
      this.target = expressionFor(next.sentiment, next.intensity);
    }
    if (next.motion !== prev.motion || next.motionKey !== prev.motionKey) {
      this.motion = next.motion ? motionFor(next.motion) : null;
      this.motionStart = this.now;
    }
    this.state = next;
  }

  /** Name of the motion currently playing, or null when idle. */
  get activeMotion(): string | null {
    return this.motion ? (this.state.motion ?? null) : null;
  }

  tick(dtMs: number): AvatarParams {
    this.now += dtMs;
    const t = this.now;
    const { reducedMotion } = this.options;

    const k = 1 - Math.exp((-EASE_PER_SECOND * dtMs) / 1000);
    for (const id of PARAM_IDS) {
      this.current[id] += (this.target[id] - this.current[id]) * k;
    }
    const out = { ...this.current };

    // Idle life: breathing always, gentle sway unless reduced motion.
    out.ParamBreath = 0.5 + 0.5 * Math.sin((t / 3500) * 2 * Math.PI);
    if (!reducedMotion) {
      out.ParamAngleX += 3 * Math.sin((t / 6100) * 2 * Math.PI);
      out.ParamAngleZ += 1.5 * Math.sin((t / 4700) * 2 * Math.PI);
      out.ParamEyeBallX += 0.15 * Math.sin((t / 5300) * 2 * Math.PI);
    }

    if (this.motion) {
      const p = (t - this.motionStart) / this.motion.durationMs;
      if (p >= 1) {
        this.motion = null;
      } else if (!reducedMotion) {
        const offsets = this.motion.sample(p);
        for (const id of PARAM_IDS) {
          const v = offsets[id];
          if (v !== undefined) out[id] += v;
        }
      }
    }

    if (this.state.speaking) {
      out.ParamMouthOpenY = Math.max(
        out.ParamMouthOpenY,
        0.15 + 0.35 * Math.abs(Math.sin(t / 90) * Math.sin(t / 230)),
      );
    }

    // Blink: eyes close and reopen over BLINK_MS, every 2.5-6s.
    if (t >= this.nextBlink) {
      const b = (t - this.nextBlink) / BLINK_MS;
      if (b >= 1) {
        this.nextBlink = t + 2500 + Math.random() * 3500;
      } else {
        const open = Math.abs(1 - 2 * b);
        out.ParamEyeLOpen *= open;
        out.ParamEyeROpen *= open;
      }
    }

    const overrides = this.state.paramOverrides;
    if (overrides) {
      for (const id of PARAM_IDS) {
        const v = overrides[id];
        if (v !== undefined) out[id] = v;
      }
    }
    return clampParams(out);
  }
}
