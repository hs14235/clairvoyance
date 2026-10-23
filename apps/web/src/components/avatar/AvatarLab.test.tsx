import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ANIMATION_TRIGGERS, SENTIMENTS } from "@/lib/avatar";
import AvatarLab from "./AvatarLab";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const avatar = () => screen.getByRole("img", { name: /avatar/i });

describe("AvatarLab", () => {
  it("can select every sentiment", async () => {
    render(<AvatarLab />);
    for (const s of SENTIMENTS) {
      await userEvent.click(screen.getByRole("button", { name: s }));
      expect(avatar().dataset.sentiment).toBe(s);
    }
  });

  it("can play every animation trigger", async () => {
    render(<AvatarLab />);
    for (const m of ANIMATION_TRIGGERS) {
      await userEvent.click(screen.getByRole("button", { name: m }));
      expect(avatar().dataset.motion).toBe(m);
    }
  });

  it("toggles speaking", async () => {
    render(<AvatarLab />);
    await userEvent.click(screen.getByLabelText(/speaking/i));
    expect(avatar().dataset.speaking).toBe("true");
  });

  it("applies an API reply to the avatar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            text_response: "I'm here.",
            sentiment: "distressed",
            intensity: 9,
            animation_trigger: "concerned_lean_in",
            human_takeover_flag: true,
          }),
        ),
      ),
    );
    render(<AvatarLab />);
    await userEvent.type(screen.getByLabelText("Test message"), "I feel hopeless");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText(/TAKEOVER/)).toBeTruthy();
    expect(avatar().dataset.sentiment).toBe("distressed");
    expect(avatar().dataset.motion).toBe("concerned_lean_in");
  });
});
