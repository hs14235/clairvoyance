import { describe, expect, it } from "vitest";

import { pickVoice } from "./speech";

const v = (name: string, lang: string, isDefault = false) =>
  ({ name, lang, default: isDefault }) as SpeechSynthesisVoice;

describe("pickVoice", () => {
  it("prefers neural English voices over the OS default", () => {
    const voices = [
      v("Microsoft David", "en-US", true),
      v("Microsoft Aria Online (Natural)", "en-US"),
      v("Google français", "fr-FR"),
    ];
    expect(pickVoice(voices)?.name).toBe("Microsoft Aria Online (Natural)");
  });

  it("falls back to the default English voice, then any English voice", () => {
    expect(pickVoice([v("Zira", "en-US"), v("David", "en-GB", true)])?.name).toBe("David");
    expect(pickVoice([v("Amélie", "fr-CA"), v("Zira", "en-US")])?.name).toBe("Zira");
  });

  it("returns undefined when there is no English voice", () => {
    expect(pickVoice([v("Amélie", "fr-CA")])).toBeUndefined();
    expect(pickVoice([])).toBeUndefined();
  });
});
