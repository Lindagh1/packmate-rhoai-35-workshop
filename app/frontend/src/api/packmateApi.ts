import {
  ApiError,
  NetworkError,
  type ChatRequest,
  type PackingResponse,
} from "../models/packmate";

export const CHAT_ENDPOINT = "/api/v1/chat";
export const CHAT_STREAM_ENDPOINT = "/api/v1/chat/stream";

export type StreamProgressStage =
  | "preparing"
  | "weather"
  | "baggage_rules"
  | "generating";

export type StreamProgressHandler = (stage: StreamProgressStage) => void;

export interface StreamChatOptions {
  signal?: AbortSignal;
  onStarted?: (traceId: string) => void;
  onProgress?: StreamProgressHandler;
  onHeartbeat?: () => void;
}

type SseHandler = (event: string, data: unknown) => void;

/** Incremental SSE parser for fragmented fetch streams. */
export class SseParser {
  private buffer = "";

  push(chunk: string, onEvent: SseHandler): void {
    this.buffer += chunk;
    let separator = this.buffer.indexOf("\n\n");
    while (separator !== -1) {
      const block = this.buffer.slice(0, separator);
      this.buffer = this.buffer.slice(separator + 2);
      this._consumeBlock(block, onEvent);
      separator = this.buffer.indexOf("\n\n");
    }
  }

  flush(onEvent: SseHandler): void {
    if (this.buffer.trim()) {
      this._consumeBlock(this.buffer, onEvent);
      this.buffer = "";
    }
  }

  private _consumeBlock(block: string, onEvent: SseHandler): void {
    const trimmed = block.trim();
    if (!trimmed || trimmed.startsWith(":")) {
      return;
    }
    let eventName = "message";
    const dataLines: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("event:")) {
        eventName = line.slice("event:".length).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice("data:".length).trim());
      }
    }
    if (!dataLines.length) {
      return;
    }
    const raw = dataLines.join("\n");
    try {
      onEvent(eventName, JSON.parse(raw) as unknown);
    } catch {
      onEvent(eventName, raw);
    }
  }
}

export async function postChat(request: ChatRequest): Promise<PackingResponse> {
  let response: Response;

  try {
    response = await fetch(CHAT_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });
  } catch {
    throw new NetworkError();
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`;

    try {
      const payload = (await response.json()) as { detail?: string | { msg?: string }[] };
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      } else if (Array.isArray(payload.detail) && payload.detail[0]?.msg) {
        detail = payload.detail.map((item) => item.msg).join(" ");
      }
    } catch {
      // Keep generic detail when response body is not JSON.
    }

    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as PackingResponse;
}

function isProgressStage(value: unknown): value is StreamProgressStage {
  return (
    value === "preparing" ||
    value === "weather" ||
    value === "baggage_rules" ||
    value === "generating"
  );
}

/**
 * Public UI path: POST SSE streaming chat with heartbeats for long LLM runs.
 */
export async function postChatStream(
  request: ChatRequest,
  options: StreamChatOptions = {},
): Promise<PackingResponse> {
  let response: Response;

  try {
    response = await fetch(CHAT_STREAM_ENDPOINT, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify(request),
      signal: options.signal,
    });
  } catch {
    if (options.signal?.aborted) {
      throw new NetworkError("Request cancelled.");
    }
    throw new NetworkError();
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (typeof payload.detail === "string") {
        detail = payload.detail;
      }
    } catch {
      // ignore
    }
    throw new ApiError(response.status, detail);
  }

  if (!response.body) {
    throw new NetworkError("Streaming response body is missing.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  const state: {
    completed: PackingResponse | null;
    streamError: ApiError | null;
  } = { completed: null, streamError: null };

  const handleEvent = (event: string, data: unknown) => {
    if (event === "started" && data && typeof data === "object") {
      const traceId = (data as { trace_id?: string }).trace_id;
      if (traceId) {
        options.onStarted?.(traceId);
      }
      return;
    }
    if (event === "progress" && data && typeof data === "object") {
      const stage = (data as { stage?: unknown }).stage;
      if (isProgressStage(stage)) {
        options.onProgress?.(stage);
      }
      return;
    }
    if (event === "heartbeat") {
      options.onHeartbeat?.();
      return;
    }
    if (event === "completed") {
      state.completed = data as PackingResponse;
      return;
    }
    if (event === "error" && data && typeof data === "object") {
      const payload = data as { message?: string; code?: string };
      state.streamError = new ApiError(
        502,
        payload.message || "Unable to complete the packing request.",
      );
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      parser.push(decoder.decode(value, { stream: true }), handleEvent);
    }
    parser.push(decoder.decode(), handleEvent);
    parser.flush(handleEvent);
  } catch {
    if (options.signal?.aborted) {
      throw new NetworkError("Request cancelled.");
    }
    throw new NetworkError();
  }

  if (state.streamError) {
    throw state.streamError;
  }
  if (!state.completed) {
    throw new NetworkError("Stream ended before a packing plan was received.");
  }
  if (!state.completed.destination || !Array.isArray(state.completed.packing_items)) {
    throw new ApiError(502, "Invalid packing plan received from stream.");
  }
  return state.completed;
}

export function progressLabel(stage: StreamProgressStage | null): string {
  switch (stage) {
    case "preparing":
      return "Preparing request…";
    case "weather":
      return "Checking weather…";
    case "baggage_rules":
      return "Checking baggage guidance…";
    case "generating":
      return "Generating packing plan…";
    default:
      return "Analyzing your trip…";
  }
}
