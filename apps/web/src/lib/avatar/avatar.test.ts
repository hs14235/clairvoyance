import { describe, expect, it } from "vitest";

import {
  ANIMATION_TRIGGERS,
  AvatarDriver,
  MOTIONS,
  NEUTRAL_PARAMS,
  PARAM_IDS,
  PARAM_RANGES,
  SENTIMENTS,
  expressionFor,
  motionFor,
  type AvatarParams,
} from ".";

// Every trigger the API's stub model can return (apps/api/src/services/qwen_service.py).
const API_TRIGGERS = [
  "idle_listen",
  "supportive_nod",
  "concerned_lean_in",
  "steady_gaze",
  "soft_smile",
  "gentle_smile",
];

function inRange(params: AvatarParams) {
  return PARAM_IDS.every((id) => {
    const [min, max] = PARAM_RANGES[id];
    return params[id] >= min && params[id] <= max;
  });
}

function run(driver: AvatarDriver, ms: number, step = 16) {
  let last = driver.tick(0);
  for (let t = 0; t < ms; t += step) last = driver.tick(step);
  return last;
}

describe("expressionFor", () => {
  it("covers every sentiment with in-range params", () => {
    for (const s of SENTIMENTS) {
      for (const i of [1, 5, 10]) expect(inRange(expressionFor(s, i))).toBe(true);
    }
  });

  it("scales with intensity", () => {
    const low = expressionFor("sad", 1);
    const high = expressionFor("sad", 10);
    expect(high.ParamBrowLAngle).toBeGreaterThan(low.ParamBrowLAngle);
    expect(low.ParamBrowLAngle).toBeGreaterThan(0);
  });

  it("smiles when calm and not when distressed", () => {
    expect(expressionFor("calm", 5).ParamMouthForm).toBeGreaterThan(0.3);
    expect(expressionFor("distressed", 9).ParamMouthForm).toBeLessThan(0);
  });
});

describe("motions", () => {
  it("defines every trigger the API can send", () => {
    for (const t of API_TRIGGERS) expect(ANIMATION_TRIGGERS).toContain(t);
  });

  it("falls back to idle for unknown triggers", () => {
    expect(motionFor("backflip")).toBeNull();
  });

  it("starts and ends each motion at rest", () => {
    for (const motion of Object.values(MOTIONS)) {
      if (!motion) continue;
      for (const t of [0, 1]) {
        for (const v of Object.values(motion.sample(t))) {
          expect(Math.abs(v as number)).toBeLessThan(1e-6);
        }
      }
    }
  });
});

describe("AvatarDriver", () => {
  it("eases toward the sentiment expression", () => {
    const d = new AvatarDriver({ reducedMotion: true });
    d.setState({ sentiment: "calm", intensity: 10, speaking: false });
    const p = run(d, 2000);
    expect(p.ParamMouthForm).toBeCloseTo(expressionFor("calm", 10).ParamMouthForm, 1);
  });

  it("plays a motion and then returns to idle", () => {
    const d = new AvatarDriver();
    d.setState({ sentiment: "neutral", intensity: 1, speaking: false, motion: "supportive_nod", motionKey: 1 });
    expect(d.activeMotion).toBe("supportive_nod");
    run(d, MOTIONS.supportive_nod!.durationMs + 100);
    expect(d.activeMotion).toBeNull();
  });

  it("replays the same motion when motionKey changes", () => {
    const d = new AvatarDriver();
    const base = { sentiment: "neutral" as const, intensity: 1, speaking: false, motion: "soft_smile" };
    d.setState({ ...base, motionKey: 1 });
    run(d, 3000);
    expect(d.activeMotion).toBeNull();
    d.setState({ ...base, motionKey: 2 });
    expect(d.activeMotion).toBe("soft_smile");
  });

  it("opens the mouth while speaking", () => {
    const d = new AvatarDriver();
    d.setState({ sentiment: "neutral", intensity: 1, speaking: true });
    let maxOpen = 0;
    d.tick(0);
    for (let i = 0; i < 100; i++) maxOpen = Math.max(maxOpen, d.tick(16).ParamMouthOpenY);
    expect(maxOpen).toBeGreaterThan(0.3);
  });

  it("lets param overrides win, clamped to range", () => {
    const d = new AvatarDriver();
    d.setState({
      sentiment: "calm",
      intensity: 10,
      speaking: true,
      paramOverrides: { ParamMouthOpenY: 0, ParamAngleX: 99 },
    });
    const p = run(d, 500);
    expect(p.ParamMouthOpenY).toBe(0);
    expect(p.ParamAngleX).toBe(30);
  });

  it("keeps every frame in range through every sentiment and motion", () => {
    const d = new AvatarDriver();
    let key = 0;
    for (const sentiment of SENTIMENTS) {
      for (const motion of ANIMATION_TRIGGERS) {
        d.setState({ sentiment, intensity: 10, speaking: true, motion, motionKey: key++ });
        for (let i = 0; i < 40; i++) expect(inRange(d.tick(50))).toBe(true);
      }
    }
  });

  it("starts at neutral", () => {
    const d = new AvatarDriver({ reducedMotion: true });
    const p = d.tick(0);
    expect(p.ParamMouthForm).toBe(NEUTRAL_PARAMS.ParamMouthForm);
  });
});
