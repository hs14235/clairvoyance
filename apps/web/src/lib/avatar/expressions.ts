import type { Sentiment } from "@/lib/api";
import { NEUTRAL_PARAMS, PARAM_IDS, type AvatarParams } from "./params";

export const SENTIMENTS: Sentiment[] = [
  "calm",
  "neutral",
  "sad",
  "anxious",
  "angry",
  "distressed",
];

// The avatar mirrors the client's state with a supportive face, not a copy of
// it: for an angry client it stays steady rather than angry.
const SENTIMENT_EXPRESSIONS: Record<Sentiment, Partial<AvatarParams>> = {
  calm: { ParamMouthForm: 0.8, ParamCheek: 0.5, ParamEyeLOpen: 0.85, ParamEyeROpen: 0.85, ParamBrowLY: 0.2, ParamBrowRY: 0.2 },
  neutral: { ParamMouthForm: 0.3 },
  sad: { ParamMouthForm: -0.45, ParamBrowLAngle: 0.7, ParamBrowRAngle: 0.7, ParamEyeLOpen: 0.8, ParamEyeROpen: 0.8, ParamAngleY: -6, ParamAngleZ: 3 },
  anxious: { ParamMouthForm: 0.2, ParamBrowLAngle: 0.5, ParamBrowRAngle: 0.5, ParamBrowLY: 0.3, ParamBrowRY: 0.3, ParamAngleZ: 2 },
  angry: { ParamMouthForm: 0, ParamBrowLY: -0.2, ParamBrowRY: -0.2, ParamEyeLOpen: 0.9, ParamEyeROpen: 0.9 },
  distressed: { ParamMouthForm: -0.1, ParamBrowLAngle: 0.9, ParamBrowRAngle: 0.9, ParamBrowLY: 0.4, ParamBrowRY: 0.4, ParamAngleY: -4, ParamAngleZ: 3, ParamEyeBallY: -0.1 },
};

/**
 * Target expression for a sentiment. Intensity (1-10) scales how far the face
 * moves from neutral: 1 is subtle, 10 is the full expression.
 */
export function expressionFor(sentiment: Sentiment, intensity: number): AvatarParams {
  const shape = SENTIMENT_EXPRESSIONS[sentiment] ?? SENTIMENT_EXPRESSIONS.neutral;
  const level = Math.min(10, Math.max(1, intensity));
  const scale = 0.4 + 0.6 * ((level - 1) / 9);
  const out = { ...NEUTRAL_PARAMS };
  for (const id of PARAM_IDS) {
    const target = shape[id];
    if (target !== undefined) {
      out[id] = NEUTRAL_PARAMS[id] + (target - NEUTRAL_PARAMS[id]) * scale;
    }
  }
  return out;
}
