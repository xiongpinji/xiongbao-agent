/**
 * OctopChatClient
 *
 * Bridges RongXinAI's IM channel handlers to Octop's dashboard chat WebSocket.
 *
 *   WS /api/agents/{agent_id}/chat/ws?token=<jwt>
 *
 * Wire protocol (mirrored from octop/src/octop/api/routers/chat/ws.py):
 *
 *   → { type: "user_turn", text, thread_id?, session_key?, model? }
 *   ← { type: "chunk",    ... }      // streaming payload
 *   ← { type: "done" }              // terminal
 *   ← { type: "error", message }   // terminal
 *   ← { type: "turn_status", ... } // optional status frame
 *
 * IM handlers only need a *single-shot* request → response text. This client
 * opens the WebSocket, sends one `user_turn`, concatenates `chunk` payloads
 * (typically `type: "text" | "delta"`) and resolves when a terminal frame is
 * observed. It is plain Node `ws` so it runs in both main process and unit
 * tests with an injected server.
 */

import WebSocket from 'ws';

export interface OctopChatClientOptions {
  baseUrl: string;
  /** JWT to authenticate with the dashboard WS endpoint. */
  bearer: string;
  /**
   * Override the WebSocket implementation — useful for tests. Defaults to the
   * `ws` package so it works under Electron's bundled Node runtime.
   */
  WebSocketCtor?: typeof WebSocket;
}

export interface SendTurnInput {
  agentId: string;
  text: string;
  threadId?: string;
  sessionKey?: string;
  model?: string;
}

export interface SendTurnResult {
  text: string;
  threadId?: string;
}

interface WsChunk {
  type?: string;
  thread_id?: string;
  delta?: string;
  content?: string;
  text?: string;
  message?: string;
}
const TERMINAL_FRAME_TYPES = new Set(['done', 'error', 'failed']);
const DEFAULT_OPEN_TIMEOUT_MS = 10_000;

export class OctopChatClient {
  private readonly baseUrl: string;
  private readonly bearer: string;
  private readonly WebSocketCtor: typeof WebSocket;

  constructor(opts: OctopChatClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, '');
    this.bearer = opts.bearer;
    this.WebSocketCtor = opts.WebSocketCtor ?? WebSocket;
  }

  /**
   * Open a WebSocket to octop, send one `user_turn`, and resolve with the
   * concatenated assistant text. Throws on transport failure, non-2xx close,
   * or an `error` frame.
   */
  async sendTurn(input: SendTurnInput, signal?: AbortSignal): Promise<SendTurnResult> {
    if (!input.agentId) throw new Error('OctopChatClient.sendTurn requires agentId');
    if (!input.text) throw new Error('OctopChatClient.sendTurn requires text');

    const wsUrl = this.buildWsUrl(input.agentId);
    const ws = new this.WebSocketCtor(wsUrl, {
      headers: { authorization: `Bearer ${this.bearer}` },
    });

    let opened = false;
    const openPromise = new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        if (!opened) reject(new Error(`OctopChatClient open timeout after ${DEFAULT_OPEN_TIMEOUT_MS}ms`));
      }, DEFAULT_OPEN_TIMEOUT_MS);
      ws.once('open', () => {
        opened = true;
        clearTimeout(timer);
        resolve();
      });
      ws.once('error', (err: Error) => {
        clearTimeout(timer);
        reject(err);
      });
    });

    if (signal) {
      signal.addEventListener('abort', () => {
        try {
          ws.close(4000, 'client-abort');
        } catch {
          // Already closed; safe to ignore.
        }
      });
    }

    try {
      await openPromise;
    } catch (err) {
      try {
        ws.close();
      } catch {
        // ignore
      }
      throw err;
    }

    const collected: string[] = [];
    let resolvedThreadId: string | undefined;

    return await new Promise<SendTurnResult>((resolve, reject) => {
      let settled = false;
      const settle = (fn: () => void): void => {
        if (settled) return;
        settled = true;
        fn();
      };

      ws.on('message', (data: unknown) => {
        const raw =
          typeof data === 'string'
            ? data
            : data instanceof Buffer
              ? data.toString('utf8')
              : Array.isArray(data)
                ? Buffer.concat(data).toString('utf8')
                : String(data);
        let payload: WsChunk | null = null;
        try {
          payload = JSON.parse(raw) as WsChunk;
        } catch {
          // Non-JSON frames are ignored.
          return;
        }
        const t = payload.type ?? '';
        if (t === 'chunk' || t === 'token') {
          // Both `chunk` (legacy dashboard style) and `token` (current harness
          // stream) carry text in `delta` / `content` / `text`. Treat them
          // identically so the IM gateway collects assistant output regardless
          // of which backend emits it.
          const text = extractChunkText(payload);
          if (text) collected.push(text);
          if (payload.thread_id) resolvedThreadId = payload.thread_id;
          return;
        }
        if (t === 'done') {
          if (payload.thread_id) resolvedThreadId = payload.thread_id;
          settle(() => {
            ws.close(1000);
            resolve({ text: collected.join(''), threadId: resolvedThreadId });
          });
          return;
        }
        if (TERMINAL_FRAME_TYPES.has(t)) {
          const message =
            payload.message ?? payload.text ?? 'Octop chat turn failed';
          settle(() => {
            ws.close(1011, message);
            reject(new Error(`OctopChatClient ${t}: ${message}`));
          });
          return;
        }
        // turn_status / pong / unknown — ignore.
      });

      ws.on('close', (code: number) => {
        if (!settled) {
          settle(() => {
            if (code === 1000) {
              resolve({ text: collected.join(''), threadId: resolvedThreadId });
            } else {
              reject(new Error(`OctopChatClient closed unexpectedly (code ${code})`));
            }
          });
        }
      });

      ws.on('error', (err: Error) => {
        settle(() => reject(err));
      });

      const turn = {
        type: 'user_turn',
        text: input.text,
        ...(input.threadId ? { thread_id: input.threadId } : {}),
        ...(input.sessionKey ? { session_key: input.sessionKey } : {}),
        ...(input.model ? { model: input.model } : {}),
      };
      ws.send(JSON.stringify(turn));
    });
  }

  private buildWsUrl(agentId: string): string {
    const base = this.baseUrl.replace(/^http/i, 'ws');
    const url = new URL(
      `/api/agents/${encodeURIComponent(agentId)}/chat/ws`,
      base.endsWith('/') ? base : `${base}/`,
    );
    url.searchParams.set('token', this.bearer);
    return url.toString();
  }
}

function extractChunkText(chunk: WsChunk): string | undefined {
  if (typeof chunk.delta === 'string') return chunk.delta;
  if (typeof chunk.content === 'string') return chunk.content;
  if (typeof chunk.text === 'string') return chunk.text;
  return undefined;
}
