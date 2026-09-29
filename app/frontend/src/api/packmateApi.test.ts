import { describe, expect, it, vi } from "vitest";
import {
  CHAT_STREAM_ENDPOINT,
  postChat,
  postChatStream,
  progressLabel,
  SseParser,
} from "../api/packmateApi";
import { ApiError, NetworkError, type ChatRequest, type PackingResponse } from "../models/packmate";

const sampleRequest: ChatRequest = {
  message: "Trip to Rome",
  traveler_profile: {
    trip_type: "leisure",
    baggage_type: "cabin",
    activities: [],
    clothing_preferences: [],
    share_sensitive_notes_with_model: false,
  },
};

const samplePacking: PackingResponse = {
  destination: "Rome",
  start_date: "2026-07-21",
  end_date: "2026-07-23",
  weather_summary: { location: "Rome", overview: "Warm." },
  packing_items: [
    {
      name: "T-shirt",
      category: "Clothing",
      quantity: 2,
      reason: "Warm weather",
      essential: true,
    },
  ],
  warnings: [],
  baggage_warnings: [],
  profile_considerations: [],
  rules_disclaimer: "Demo",
  language: "fr",
};

function encodeSse(frames: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index >= frames.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(frames[index]));
      index += 1;
    },
  });
}

describe("postChat", () => {
  it("calls POST /api/v1/chat with a JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => samplePacking,
    });
    vi.stubGlobal("fetch", fetchMock);

    await postChat(sampleRequest);

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(sampleRequest),
    });
  });

  it("throws ApiError for backend failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: "LLM is not configured." }),
      }),
    );

    await expect(postChat(sampleRequest)).rejects.toEqual(
      new ApiError(503, "LLM is not configured."),
    );
  });

  it("throws NetworkError when fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(postChat(sampleRequest)).rejects.toBeInstanceOf(NetworkError);
  });
});

describe("SseParser", () => {
  it("parses a fragmented event across chunks", () => {
    const parser = new SseParser();
    const events: Array<{ event: string; data: unknown }> = [];
    const onEvent = (event: string, data: unknown) => events.push({ event, data });

    parser.push("event: start", onEvent);
    parser.push("ed\ndata: {\"status\":\"processing\"", onEvent);
    parser.push("}\n\n", onEvent);

    expect(events).toEqual([{ event: "started", data: { status: "processing" } }]);
  });

  it("parses multiple events in one chunk and ignores keepalive comments", () => {
    const parser = new SseParser();
    const events: Array<{ event: string; data: unknown }> = [];
    const onEvent = (event: string, data: unknown) => events.push({ event, data });

    parser.push(
      [
        "event: started",
        'data: {"status":"processing","trace_id":"abc"}',
        "",
        ": keepalive",
        "",
        "event: progress",
        'data: {"stage":"weather"}',
        "",
        "event: heartbeat",
        'data: {"status":"processing"}',
        "",
        "",
      ].join("\n"),
      onEvent,
    );
    parser.flush(onEvent);

    expect(events.map((item) => item.event)).toEqual(["started", "progress", "heartbeat"]);
    expect(events[1].data).toEqual({ stage: "weather" });
  });
});

describe("postChatStream", () => {
  it("posts to the streaming endpoint and returns completed PackingResponse", async () => {
    const frames = [
      'event: started\ndata: {"status":"processing","trace_id":"t1"}\n\n',
      'event: progress\ndata: {"stage":"weather"}\n\n',
      `event: completed\ndata: ${JSON.stringify(samplePacking)}\n\n`,
    ];
    const stages: string[] = [];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      body: encodeSse(frames),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await postChatStream(sampleRequest, {
      onProgress: (stage) => stages.push(stage),
    });

    expect(fetchMock).toHaveBeenCalledWith(
      CHAT_STREAM_ENDPOINT,
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        }),
        body: JSON.stringify(sampleRequest),
      }),
    );
    expect(result.destination).toBe("Rome");
    expect(stages).toEqual(["weather"]);
  });

  it("surfaces sanitized stream errors", async () => {
    const frames = [
      'event: started\ndata: {"status":"processing","trace_id":"t1"}\n\n',
      'event: error\ndata: {"code":"agent_error","message":"Unable to complete the packing request.","trace_id":"t1"}\n\n',
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: encodeSse(frames),
      }),
    );

    await expect(postChatStream(sampleRequest)).rejects.toEqual(
      new ApiError(502, "Unable to complete the packing request."),
    );
  });

  it("throws when the stream ends without completed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: encodeSse(['event: started\ndata: {"status":"processing"}\n\n']),
      }),
    );

    await expect(postChatStream(sampleRequest)).rejects.toBeInstanceOf(NetworkError);
  });

  it("supports cancellation via AbortSignal", async () => {
    const controller = new AbortController();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => {
        controller.abort();
        return Promise.reject(new DOMException("Aborted", "AbortError"));
      }),
    );

    await expect(
      postChatStream(sampleRequest, { signal: controller.signal }),
    ).rejects.toBeInstanceOf(NetworkError);
  });

  it("does not use localStorage or sessionStorage", async () => {
    const localSpy = vi.spyOn(Storage.prototype, "setItem");
    const frames = [
      'event: started\ndata: {"status":"processing","trace_id":"t1"}\n\n',
      `event: completed\ndata: ${JSON.stringify(samplePacking)}\n\n`,
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: encodeSse(frames),
      }),
    );

    await postChatStream(sampleRequest);
    expect(localSpy).not.toHaveBeenCalled();
    localSpy.mockRestore();
  });
});

describe("progressLabel", () => {
  it("maps stages to sober UI labels", () => {
    expect(progressLabel(null)).toMatch(/Analyzing/i);
    expect(progressLabel("weather")).toMatch(/weather/i);
    expect(progressLabel("baggage_rules")).toMatch(/baggage/i);
  });
});
