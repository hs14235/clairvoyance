// Avatar parameters use Live2D Cubism's standard parameter IDs, so a Live2D
// model can later be driven by the same values (model.setParameterValueById).

export const PARAM_RANGES = {
  ParamAngleX: [-30, 30], // head turn left/right
  ParamAngleY: [-30, 30], // head tilt up/down
  ParamAngleZ: [-30, 30], // head roll
  ParamEyeLOpen: [0, 1],
  ParamEyeROpen: [0, 1],
  ParamEyeBallX: [-1, 1],
  ParamEyeBallY: [-1, 1],
  ParamBrowLY: [-1, 1], // brow height
  ParamBrowRY: [-1, 1],
  ParamBrowLAngle: [-1, 1], // +1 = inner end raised (worried)
  ParamBrowRAngle: [-1, 1],
  ParamMouthForm: [-1, 1], // -1 frown, +1 smile
  ParamMouthOpenY: [0, 1],
  ParamCheek: [0, 1], // blush
  ParamBodyAngleX: [-10, 10],
  ParamBreath: [0, 1],
} as const satisfies Record<string, readonly [number, number]>;

export type ParamId = keyof typeof PARAM_RANGES;
export type AvatarParams = Record<ParamId, number>;

export const PARAM_IDS = Object.keys(PARAM_RANGES) as ParamId[];

export const NEUTRAL_PARAMS: AvatarParams = {
  ParamAngleX: 0,
  ParamAngleY: 0,
  ParamAngleZ: 0,
  ParamEyeLOpen: 1,
  ParamEyeROpen: 1,
  ParamEyeBallX: 0,
  ParamEyeBallY: 0,
  ParamBrowLY: 0,
  ParamBrowRY: 0,
  ParamBrowLAngle: 0,
  ParamBrowRAngle: 0,
  ParamMouthForm: 0,
  ParamMouthOpenY: 0,
  ParamCheek: 0,
  ParamBodyAngleX: 0,
  ParamBreath: 0,
};

export function clampParam(id: ParamId, value: number): number {
  const [min, max] = PARAM_RANGES[id];
  return Math.min(max, Math.max(min, value));
}

export function clampParams(params: AvatarParams): AvatarParams {
  const out = { ...params };
  for (const id of PARAM_IDS) out[id] = clampParam(id, out[id]);
  return out;
}
