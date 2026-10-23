import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatMessageResponse } from "@/lib/api";
import Chat from "./Chat";

// Minimal MediaRecorder: emits one chunk and fires onstop when stopped.
class FakeRecorder {
  static isTypeSupported = (t: string) => t === "audio/webm;codecs=opus";
  mimeType: string;
  ondataavailable: ((e: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  constructor(
    public stream: MediaStream,
    opts?: { mimeType?: string },
  ) {
    this.mimeType = opts?.mimeType ?? "";
  }
  start() {}
  stop() {
    this.ondataavailable?.({ data: new Blob(["voice"], { type: this.mimeType }) });
    this.onstop?.();
  }
}

const stopTrack = vi.fn();

function stubMic(getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] })) {
  vi.stubGlobal("MediaRecorder", FakeRecorder);
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia },
  });
  return getUserMedia;
}

const reply: ChatMessageResponse = {
  text_response: "That sounds like a lot.",
  sentiment: "anxious",
  intensity: 4,
  animation_trigger: "supportive_nod",
  human_takeover_flag: false,
};

function json(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200 });
}

beforeEach(() => stopTrack.mockClear());

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  Reflect.deleteProperty(navigator, "mediaDevices");
});

describe("MicButton in Chat", () => {
  it("is hidden when the browser can't record", () => {
    render(<Chat />);
    expect(screen.queryByRole("button", { name: /record voice/i })).toBeNull();
  });

  it("records, uploads the audio, then sends the transcript as a chat message", async () => {
    stubMic();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(json({ text: "exams are stressing me out" }))
      .mockResolvedValueOnce(json(reply));
    vi.stubGlobal("fetch", fetchMock);
    render(<Chat />);

    await userEvent.click(screen.getByRole("button", { name: "Record voice message" }));
    const stop = screen.getByRole("button", { name: "Stop recording" });
    expect(stop.getAttribute("aria-pressed")).toBe("true");
    await userEvent.click(stop);

    expect(await screen.findByText("That sounds like a lot.")).toBeTruthy();
    expect(screen.getByText("exams are stressing me out")).toBeTruthy();
    expect(stopTrack).toHaveBeenCalled(); // mic released

    const [sttUrl, sttInit] = fetchMock.mock.calls[0];
    expect(sttUrl).toBe("http://localhost:8000/api/v1/speech/transcribe");
    const audio = (sttInit.body as FormData).get("audio") as File;
    expect(audio.name).toBe("speech.webm");
    expect(audio.type).toBe("audio/webm;codecs=opus");

    const [chatUrl, chatInit] = fetchMock.mock.calls[1];
    expect(chatUrl).toBe("http://localhost:8000/api/v1/chat/message");
    expect(JSON.parse(chatInit.body).message).toBe("exams are stressing me out");
  });

  it("explains when microphone permission is denied", async () => {
    stubMic(vi.fn().mockRejectedValue(new DOMException("denied", "NotAllowedError")));
    render(<Chat />);

    await userEvent.click(screen.getByRole("button", { name: "Record voice message" }));

    expect(await screen.findByText(/microphone access was blocked/i)).toBeTruthy();
  });

  it("shows an error and sends nothing when transcription fails", async () => {
    stubMic();
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response("", { status: 500 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<Chat />);

    await userEvent.click(screen.getByRole("button", { name: "Record voice message" }));
    await userEvent.click(screen.getByRole("button", { name: "Stop recording" }));

    expect(await screen.findByText(/couldn't transcribe/i)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("Speak replies", () => {
  it("reads the reply aloud only when the toggle is on", async () => {
    const speakMock = vi.fn();
    vi.stubGlobal("speechSynthesis", { speak: speakMock, cancel: vi.fn() });
    vi.stubGlobal(
      "SpeechSynthesisUtterance",
      class {
        constructor(public text: string) {}
      },
    );
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(json(reply)).mockResolvedValueOnce(json(reply)));
    render(<Chat />);

    await userEvent.type(screen.getByLabelText("Message"), "hi");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByText("That sounds like a lot.");
    expect(speakMock).not.toHaveBeenCalled();

    await userEvent.click(screen.getByLabelText("Speak replies aloud"));
    await userEvent.type(screen.getByLabelText("Message"), "again");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(speakMock).toHaveBeenCalledTimes(1));
    expect(speakMock.mock.calls[0][0].text).toBe("That sounds like a lot.");
  });
});
