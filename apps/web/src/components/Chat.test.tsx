import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ChatMessageResponse } from "@/lib/api";
import Chat from "./Chat";

function reply(overrides: Partial<ChatMessageResponse> = {}): ChatMessageResponse {
  return {
    text_response: "I hear you.",
    sentiment: "anxious",
    intensity: 4,
    animation_trigger: "supportive_nod",
    human_takeover_flag: false,
    ...overrides,
  };
}

function mockFetch(...bodies: ChatMessageResponse[]) {
  const fetchMock = vi.fn();
  for (const body of bodies) {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify(body), { status: 200 }),
    );
  }
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function send(text: string) {
  await userEvent.type(screen.getByLabelText("Message"), text);
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Chat", () => {
  it("posts the message and shows the reply with sentiment and intensity", async () => {
    const fetchMock = mockFetch(reply());
    render(<Chat />);

    await send("exams are stressing me out");

    expect(await screen.findByText("I hear you.")).toBeTruthy();
    expect(screen.getByText("exams are stressing me out")).toBeTruthy();
    expect(screen.getByText("anxious")).toBeTruthy();
    expect(screen.getByLabelText("Intensity 4 of 10")).toBeTruthy();

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/v1/chat/message");
    const body = JSON.parse(init.body);
    expect(body.message).toBe("exams are stressing me out");
    expect(typeof body.session_id).toBe("string");
  });

  it("drives the avatar from the reply's sentiment and animation trigger", async () => {
    mockFetch(reply({ sentiment: "sad", intensity: 6, animation_trigger: "soft_smile" }));
    render(<Chat />);

    const avatar = screen.getByRole("img", { name: /avatar/i });
    expect(avatar.dataset.sentiment).toBe("neutral");

    await send("I've been feeling down");
    await screen.findByText("I hear you.");

    expect(avatar.dataset.sentiment).toBe("sad");
    expect(avatar.dataset.intensity).toBe("6");
    expect(avatar.dataset.motion).toBe("soft_smile");
    expect(avatar.dataset.speaking).toBe("true");
  });

  it("reuses the same session id across messages", async () => {
    const fetchMock = mockFetch(reply(), reply({ text_response: "Go on." }));
    render(<Chat />);

    await send("first");
    await screen.findByText("I hear you.");
    await send("second");
    await screen.findByText("Go on.");

    const ids = fetchMock.mock.calls.map(([, init]) => JSON.parse(init.body).session_id);
    expect(ids[0]).toBe(ids[1]);
  });

  it("has no takeover banner for a low-intensity reply", async () => {
    mockFetch(reply());
    render(<Chat />);

    await send("hello");
    await screen.findByText("I hear you.");

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows the takeover banner when the API flags the session and keeps it", async () => {
    mockFetch(
      reply({ sentiment: "distressed", intensity: 9, human_takeover_flag: true }),
      reply({ text_response: "Still here." }),
    );
    render(<Chat />);

    await send("I feel hopeless");
    const banner = await screen.findByRole("alert");
    expect(banner.textContent).toMatch(/counselor has been notified/i);

    await send("ok");
    await screen.findByText("Still here.");
    expect(screen.getByRole("alert")).toBeTruthy();
  });

  it("shows an error when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<Chat />);

    await send("hello");

    expect(await screen.findByText(/couldn't reach the server/i)).toBeTruthy();
  });
});
