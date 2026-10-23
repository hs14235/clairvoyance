import type { AvatarParams } from "./params";

/** A one-shot gesture: additive offsets sampled over normalized time 0..1. */
export interface Motion {
  durationMs: number;
  sample(t: number): Partial<AvatarParams>;
}

// Rises 0 -> 1 -> 0 over t in 0..1.
const bell = (t: number) => Math.sin(Math.PI * t);
// Rises fast, holds, eases out.
const hold = (t: number) => Math.min(1, t * 5, (1 - t) * 4);

// Keys are the animation_trigger values the API returns
// (apps/api/src/services/qwen_service.py).
export const MOTIONS: Record<string, Motion | null> = {
  idle_listen: null,
  supportive_nod: {
    durationMs: 1400,
    sample: (t) => ({ ParamAngleY: -12 * Math.sin(4 * Math.PI * t) * (1 - t), ParamEyeLOpen: -0.1 * bell(t), ParamEyeROpen: -0.1 * bell(t) }),
  },
  concerned_lean_in: {
    durationMs: 2600,
    sample: (t) => ({ ParamBodyAngleX: 4 * hold(t), ParamAngleZ: 6 * hold(t), ParamAngleY: -5 * hold(t), ParamBrowLAngle: 0.3 * hold(t), ParamBrowRAngle: 0.3 * hold(t) }),
  },
  steady_gaze: {
    durationMs: 2000,
    sample: (t) => ({ ParamAngleX: 0, ParamEyeBallX: 0, ParamEyeBallY: 0, ParamBrowLY: -0.1 * hold(t), ParamBrowRY: -0.1 * hold(t) }),
  },
  soft_smile: {
    durationMs: 1800,
    sample: (t) => ({ ParamMouthForm: 0.4 * hold(t), ParamCheek: 0.3 * hold(t), ParamAngleZ: 4 * bell(t) }),
  },
  gentle_smile: {
    durationMs: 1600,
    sample: (t) => ({ ParamMouthForm: 0.5 * hold(t), ParamCheek: 0.4 * hold(t), ParamEyeLOpen: -0.3 * hold(t), ParamEyeROpen: -0.3 * hold(t) }),
  },
};

export const ANIMATION_TRIGGERS = Object.keys(MOTIONS);

/** Unknown triggers (e.g. a new one from the model) fall back to idle. */
export function motionFor(trigger: string): Motion | null {
  return MOTIONS[trigger] ?? null;
}
