/**
 * Type stub for the `ws` package — the runtime library ships only JS. We use
 * a tiny subset (`new WebSocket(url, { headers })`) so a single ambient
 * declaration is enough for `OctopChatClient` and any future callers.
 */
declare module 'ws' {
  interface WebSocketConstructorOptions {
    headers?: Record<string, string>;
    [key: string]: unknown;
  }
  type RawData = Buffer | string | Uint8Array | ArrayBuffer | Buffer[];
  interface WebSocketInstance {
    on(event: 'open' | 'close' | 'error' | 'message', listener: (...args: unknown[]) => void): this;
    once(event: 'open' | 'close' | 'error' | 'message', listener: (...args: unknown[]) => void): this;
    removeAllListeners(): this;
    send(data: string): void;
    close(code?: number, reason?: string): void;
  }
  class WebSocket implements WebSocketInstance {
    constructor(url: string, options?: WebSocketConstructorOptions);
    on(event: string, listener: (...args: unknown[]) => void): this;
    once(event: string, listener: (...args: unknown[]) => void): this;
    removeAllListeners(): this;
    send(data: string): void;
    close(code?: number, reason?: string): void;
  }
  export = WebSocket;
}
