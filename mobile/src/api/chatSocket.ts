/**
 * Wraps the Octop chat WebSocket.
 *
 * Endpoint: `${baseUrl}/api/agents/{agent_id}/chat/ws?token={token}`
 *
 * Frame protocol (matches the desktop dashboard):
 *   client → server:
 *     {type: "user_turn", text, attachments?, thread_id?}
 *     {type: "ping"}
 *   server → client:
 *     {type: "chunk", text}
 *     {type: "tool_start", tool, tool_hint_text?}
 *     {type: "tool_end", tool}
 *     {type: "message", role, text}
 *     {type: "error", message}
 *     {type: "done"}
 *     {type: "pong"}
 *
 * The transport is injected via `WebSocketCtor` for unit tests.
 */

export type IncomingFrame =
  | { type: 'chunk'; text: string }
  | { type: 'message'; role: string; text: string }
  | { type: 'tool_start'; tool: string; tool_hint_text?: string }
  | { type: 'tool_end'; tool: string }
  | { type: 'error'; message: string }
  | { type: 'done' }
  | { type: 'pong' }
  | { type: string; [k: string]: unknown };

export interface OctopChatSocketOptions {
  baseUrl: string;
  token: string;
  agentId: string;
  WebSocketCtor?: typeof WebSocket;
  onFrame?: (frame: IncomingFrame) => void;
  onOpen?: () => void;
  onClose?: (code: number, reason: string) => void;
  onError?: (err: Error) => void;
}

export class OctopChatSocket {
  private ws: WebSocket | null = null;
  private closed = false;

  constructor(private readonly options: OctopChatSocketOptions) {}

  open(): void {
    if (this.closed) return;
    const Ctor = this.options.WebSocketCtor ?? WebSocket;
    const base = this.options.baseUrl.replace(/\/+$/, '');
    const wsProtocol = base.startsWith('https://') ? 'wss://' : 'ws://';
    const host = base.replace(/^https?:\/\//, '');
    const url =
      `${wsProtocol}${host}/api/agents/${encodeURIComponent(this.options.agentId)}` +
      `/chat/ws?token=${encodeURIComponent(this.options.token)}`;
    const ws = new Ctor(url);
    this.ws = ws;
    ws.addEventListener('open', () => this.options.onOpen?.());
    ws.addEventListener('message', (event: MessageEvent) => {
      try {
        const frame = JSON.parse(typeof event.data === 'string' ? event.data : '');
        if (frame && typeof frame === 'object') {
          this.options.onFrame?.(frame as IncomingFrame);
        }
      } catch (err) {
        this.options.onError?.(err instanceof Error ? err : new Error(String(err)));
      }
    });
    ws.addEventListener('error', () => {
      this.options.onError?.(new Error('WebSocket error'));
    });
    ws.addEventListener('close', (event: CloseEvent) => {
      this.options.onClose?.(event.code, event.reason);
    });
  }

  send(text: string, threadId?: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('chat socket is not open');
    }
    const frame = { type: 'user_turn', text, thread_id: threadId };
    this.ws.send(JSON.stringify(frame));
  }

  ping(): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({ type: 'ping' }));
  }

  close(): void {
    this.closed = true;
    this.ws?.close();
    this.ws = null;
  }
}
