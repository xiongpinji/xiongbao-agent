/**
 * OctopBackendSseClient
 *
 * Tiny SSE client that talks to an Octop / workbuddy-style backend:
 *   POST /api/tasks                 → { task_id }
 *   GET  /api/tasks/{id}/events?after=N  → text/event-stream of framed events.
 *
 * Each frame is encoded by `iter_sse_frames` (octop/contrib/workbuddy/console_events.py):
 *
 *     id: <n>
 *     event: <kind>
 *     data: <json payload>
 *
 * The terminal kinds ("done", "failed", "error", "accepted", "completed") end the stream.
 *
 * This client is the smallest possible bridge so the renderer/main process can
 * consume Octop task events without depending on the workbuddy Python package
 * directly. It deliberately exposes only what we need today:
 *
 *   - startTask({ prompt, ... }) → Promise<{ taskId }>
 *   - streamTaskEvents(taskId, after?) → AsyncIterable<OctopSseEvent>
 *   - parseSseBuffer(buffer) → { events, remainder } (tested in isolation)
 *
 * The class intentionally knows nothing about RongXinAI's PiRuntimeAdapter or
 * Electron — it is plain Node and unit-testable.
 */

import type { IncomingMessage } from 'node:http';
import type { Buffer } from 'node:buffer';

export interface OctopSseEvent {
  /** Sequential index from the upstream `_i` field. */
  id: number;
  /** Frame kind, e.g. "message", "tool_call", "done". */
  event: string;
  /** Decoded JSON payload (may be any shape, never null). */
  data: unknown;
  /** True if the event indicates the stream has ended. */
  terminal: boolean;
}

const TERMINAL_KINDS = new Set([
  'done',
  'failed',
  'error',
  'accepted',
  'completed',
  'timeout',
]);

/** Split a buffered chunk into complete SSE frames plus any trailing bytes. */
export function parseSseBuffer(buffer: string): { events: OctopSseEvent[]; remainder: string } {
  const events: OctopSseEvent[] = [];
  // Frames are separated by a blank line.
  let cut: number;
  while ((cut = buffer.indexOf('\n\n')) !== -1) {
    const raw = buffer.slice(0, cut);
    buffer = buffer.slice(cut + 2);
    const ev = parseOneFrame(raw);
    if (ev) events.push(ev);
  }
  return { events, remainder: buffer };
}

function parseOneFrame(rawFrame: string): OctopSseEvent | null {
  let id = 0;
  let event = 'message';
  let data: unknown = null;
  let sawData = false;
  const lines = rawFrame.split(/\r?\n/);
  for (const line of lines) {
    if (!line || line.startsWith(':')) continue; // comment / heartbeat
    const sep = line.indexOf(':');
    if (sep === -1) continue;
    const field = line.slice(0, sep).trim();
    let value = line.slice(sep + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    switch (field) {
      case 'id':
        id = Number.parseInt(value, 10) || 0;
        break;
      case 'event':
        event = value;
        break;
      case 'data':
        sawData = true;
        try {
          data = JSON.parse(value);
        } catch {
          data = value;
        }
        break;
      default:
        break;
    }
  }
  if (!sawData && event === 'message') return null; // comment-only frame
  const terminal =
    (typeof data === 'object' && data !== null && (data as { terminal?: boolean }).terminal === true) ||
    TERMINAL_KINDS.has(event);
  return { id, event, data, terminal };
}

export interface OctopBackendSseClientOptions {
  baseUrl: string;
  /** Authorization header value (e.g. "Bearer …"). Optional. */
  bearer?: string;
  /** Injectable fetch — defaults to global `fetch`. */
  fetchImpl?: typeof fetch;
}

export interface StartTaskInput {
  prompt: string;
  title?: string;
  project_id?: string;
  [extra: string]: unknown;
}

export class OctopBackendSseClient {
  private readonly baseUrl: string;
  private readonly bearer: string | undefined;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: OctopBackendSseClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, '');
    this.bearer = opts.bearer;
    this.fetchImpl = opts.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { 'content-type': 'application/json' };
    if (this.bearer) h.authorization = this.bearer;
    return h;
  }

  /** Submit a new task and return its server-assigned id. */
  async startTask(input: StartTaskInput): Promise<{ taskId: string }> {
    const res = await this.fetchImpl(`${this.baseUrl}/api/tasks`, {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify(input),
    });
    if (!res.ok) {
      throw new Error(`Octop startTask HTTP ${res.status}: ${await res.text()}`);
    }
    const json = (await res.json()) as { task_id?: string; id?: string };
    const taskId = json.task_id ?? json.id;
    if (!taskId) throw new Error('Octop startTask response missing task_id');
    return { taskId };
  }

  /** Resume a stream starting at `after`. */
  async fetchEventStream(
    taskId: string,
    after = 0,
    signal?: AbortSignal,
  ): Promise<ReadableStream<Uint8Array> | null> {
    const url = `${this.baseUrl}/api/tasks/${encodeURIComponent(taskId)}/events?after=${after}`;
    const res = await this.fetchImpl(url, {
      method: 'GET',
      headers: this.bearer ? { authorization: this.bearer } : {},
      signal,
    });
    if (!res.ok) throw new Error(`Octop stream HTTP ${res.status}`);
    return res.body;
  }

  /**
   * Stream events for a task. Iterates until a terminal event is observed or
   * the underlying stream ends. `signal` cancels the subscription.
   */
  async *streamTaskEvents(
    taskId: string,
    after = 0,
    signal?: AbortSignal,
  ): AsyncGenerator<OctopSseEvent> {
    const body = await this.fetchEventStream(taskId, after, signal);
    if (!body) return;
    const reader = body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buf = '';
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const { events, remainder } = parseSseBuffer(buf);
        buf = remainder;
        for (const ev of events) {
          yield ev;
          if (ev.terminal) return;
        }
      }
      // Drain whatever is left.
      if (buf.length > 0) {
        const { events } = parseSseBuffer(buf + '\n\n');
        for (const ev of events) yield ev;
      }
    } finally {
      try {
        reader.releaseLock();
      } catch {
        // ignore
      }
    }
  }
}

/** Convenience: parse an HTTP IncomingMessage stream into SSE events. */
export async function* eventsFromIncoming(
  res: IncomingMessage,
  signal?: AbortSignal,
): AsyncGenerator<OctopSseEvent> {
  let buf = '';
  for await (const chunk of res as AsyncIterable<Buffer>) {
    if (signal?.aborted) return;
    buf += chunk.toString('utf-8');
    const { events, remainder } = parseSseBuffer(buf);
    buf = remainder;
    for (const ev of events) {
      yield ev;
      if (ev.terminal) return;
    }
  }
}
