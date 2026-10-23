import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SessionDetail, SessionSummary } from "@/lib/sessions";
import Dashboard from "./Dashboard";

const BASE = "http://localhost:8000/api/v1/sessions";

function summary(overrides: Partial<SessionSummary> = {}): SessionSummary {
  const now = new Date().toISOString();
  return {
    id: "aaaaaaaa-1111",
    status: "ai",
    sentiment: "anxious",
    intensity: 4,
    peak_intensity: 4,
    message_count: 2,
    last_client_message: "I'm worried about exams",
    created_at: now,
    updated_at: now,
    flagged_at: null,
    taken_over_at: null,
    ...overrides,
  };
}

function detail(overrides: Partial<SessionDetail> = {}): SessionDetail {
  const now = new Date().toISOString();
  return {
    ...summary(),
    messages: [
      { role: "client", text: "I feel hopeless", at: now, sentiment: null, intensity: null },
      { role: "ai", text: "I'm glad you told me.", at: now, sentiment: "distressed", intensity: 9 },
    ],
    ...overrides,
  };
}

// Routes fetch calls by URL + method so polling order doesn't matter.
function mockApi(routes: Record<string, unknown>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url}`;
    if (!(key in routes)) return new Response("not found", { status: 404 });
    return new Response(JSON.stringify(routes[key]), { status: 200 });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Dashboard", () => {
  it("lists sessions in API order with status labels", async () => {
    mockApi({
      [`GET ${BASE}`]: [
        summary({ id: "flagged-1", status: "flagged", intensity: 9, peak_intensity: 9 }),
        summary({ id: "calm-2", last_client_message: "hello" }),
      ],
    });
    render(<Dashboard />);

    const rows = await screen.findAllByRole("button", { name: /ago/ });
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText("Needs counselor")).toBeTruthy();
    expect(within(rows[1]).getByText("AI")).toBeTruthy();
    expect(screen.getByText("2 active · 1 need a counselor")).toBeTruthy();
  });

  it("shows the transcript and takes over the selected session", async () => {
    const flagged = summary({ id: "flagged-1", status: "flagged" });
    const fetchMock = mockApi({
      [`GET ${BASE}`]: [flagged],
      [`GET ${BASE}/flagged-1`]: detail({ id: "flagged-1", status: "flagged" }),
      [`POST ${BASE}/flagged-1/takeover`]: detail({ id: "flagged-1", status: "counselor" }),
    });
    render(<Dashboard />);

    await userEvent.click(await screen.findByRole("button", { name: /ago/ }));
    expect(await screen.findByText("I feel hopeless")).toBeTruthy();

    await userEvent.click(screen.getByRole("button", { name: "Take over" }));
    expect(await screen.findByRole("button", { name: "Hand back to AI" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(`${BASE}/flagged-1/takeover`, { method: "POST" });
  });

  it("releases a session the counselor holds", async () => {
    const fetchMock = mockApi({
      [`GET ${BASE}`]: [summary({ id: "held", status: "counselor" })],
      [`GET ${BASE}/held`]: detail({ id: "held", status: "counselor" }),
      [`POST ${BASE}/held/release`]: detail({ id: "held", status: "ai" }),
    });
    render(<Dashboard />);

    await userEvent.click(await screen.findByRole("button", { name: /ago/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Hand back to AI" }));

    expect(await screen.findByRole("button", { name: "Take over" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith(`${BASE}/held/release`, { method: "POST" });
  });

  it("shows an error when the API is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<Dashboard />);
    expect(await screen.findByText(/couldn't reach the api/i)).toBeTruthy();
  });
});
