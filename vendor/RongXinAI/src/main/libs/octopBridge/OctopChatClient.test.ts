/**
 * Unit tests for OctopChatClient.
 *
 * Uses a fake WebSocket so we don't need a real Octop server. The fake is
 * driven synchronously by the test: the test calls `fake.open()` to fire the
 * `open` event, then `fake.send(...)` to assert what the client transmitted,
 * then `fake.receive(...)` to feed server frames back, and finally `fake.close()`
 * to end the WS.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { OctopChatClient } from './OctopChatClient';
import type { OctopChatClientOptions } from './OctopChatClient';

type WsListener = (...args: unknown[]) => void;

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];

  url: string;
  headers: Record<string, string>;
  readyState = 0;
  sentFrames: string[] = [];
  closed = false;
  closeCode?: number;
  closeReason?: string;
  private listeners = new Map<string, WsListener[]>();

  constructor(url: string, opts?: { headers?: Record<string, string> }) {
    this.url = url;
    this.headers = opts?.headers ?? {};
    FakeWebSocket.instances.push(this);
  }

  on(event: string, listener: WsListener): this {
    (this.listeners.get(event) ?? this.listeners.set(event, []).get(event)!).push(listener);
    return this;
  }
  once(event: string, listener: WsListener): this {
    const wrap: WsListener = (...args) => {
      this.removeListener(event, wrap);
      listener(...args);
    };
    return this.on(event, wrap);
  }
  removeListener(event: string, listener?: WsListener): this {
    if (!listener) {
      this.listeners.delete(event);
      return this;
    }
    const arr = this.listeners.get(event) ?? [];
    this.listeners.set(
      event,
      arr.filter(l => l !== listener),
    );
    return this;
  }
  emit(event: string, ...args: unknown[]): void {
    for (const l of [...(this.listeners.get(event) ?? [])]) l(...args);
  }

  send(frame: string): void {
    this.sentFrames.push(frame);
  }

  close(code?: number, reason?: string): void {
    this.closed = true;
    this.closeCode = code;
    this.closeReason = reason;
    this.readyState = 3;
    this.emit('close', code ?? 1000);
  }

  open(): void {
    this.readyState = 1;
    this.emit('open');
  }

  receive(payload: unknown): void {
    const text = typeof payload === 'string' ? payload : JSON.stringify(payload);
    this.emit('message', Buffer.from(text));
  }

  errorOut(err: Error): void {
    this.emit('error', err);
  }
}

function makeClient(bearer = 'jwt-xyz'): OctopChatClient {
  const opts: OctopChatClientOptions = {
    baseUrl: 'http://octop.local:8080',
    bearer,
    WebSocketCtor: FakeWebSocket as unknown as OctopChatClientOptions['WebSocketCtor'],
  };
  return new OctopChatClient(opts);
}

describe('OctopChatClient', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
  });

  afterEach(() => {
    FakeWebSocket.instances = [];
  });

  it('builds the right WS URL with token query and Bearer header', async () => {
    const client = makeClient('jwt-abc');
    const promise = client.sendTurn({ agentId: 'ag-9', text: 'hi' });
    const fake = FakeWebSocket.instances[0];
    expect(fake.url).toContain('/api/agents/ag-9/chat/ws');
    expect(fake.url).toContain('token=jwt-abc');
    expect(fake.headers.authorization).toBe('Bearer jwt-abc');
    fake.open();
    await Promise.resolve(); // let `await openPromise` flush and register message listener
    fake.receive({ type: 'done' });
    await promise;
  });

  it('sends user_turn with text/threadId/model and concatenates chunk deltas', async () => {
    const client = makeClient();
    const promise = client.sendTurn({
      agentId: 'ag-1',
      text: 'hello',
      threadId: 't-42',
      model: 'openai/gpt-4o',
    });
    const fake = FakeWebSocket.instances[0];
    fake.open();
    await Promise.resolve();
    fake.receive({ type: 'chunk', delta: 'Hi ' });
    fake.receive({ type: 'chunk', delta: 'there' });
    fake.receive({ type: 'done', thread_id: 't-42' });

    const result = await promise;
    expect(fake.sentFrames).toHaveLength(1);
    const sent = JSON.parse(fake.sentFrames[0]) as Record<string, unknown>;
    expect(sent.type).toBe('user_turn');
    expect(sent.text).toBe('hello');
    expect(sent.thread_id).toBe('t-42');
    expect(sent.model).toBe('openai/gpt-4o');
    expect(result.text).toBe('Hi there');
    expect(result.threadId).toBe('t-42');
    expect(fake.closeCode).toBe(1000);
  });

  it('collects assistant text from `token` frames (current harness stream shape)', async () => {
    const client = makeClient();
    const promise = client.sendTurn({ agentId: 'ag-1', text: 'hi' });
    const fake = FakeWebSocket.instances[0];
    fake.open();
    await Promise.resolve();
    fake.receive({ type: 'token', content: '你' });
    fake.receive({ type: 'token', content: '好' });
    fake.receive({ type: 'done', thread_id: 't-7' });
    const result = await promise;
    expect(result.text).toBe('你好');
    expect(result.threadId).toBe('t-7');
  });

  it('rejects when octop replies with an error frame', async () => {
    const client = makeClient();
    const promise = client.sendTurn({ agentId: 'ag-1', text: 'hi' });
    const fake = FakeWebSocket.instances[0];
    fake.open();
    await Promise.resolve();
    fake.receive({ type: 'error', message: 'agent offline' });
    await expect(promise).rejects.toThrow(/agent offline/);
  });

  it('rejects when transport reports an error before open', async () => {
    const client = makeClient();
    const promise = client.sendTurn({ agentId: 'ag', text: 'x' });
    const fake = FakeWebSocket.instances[0];
    fake.errorOut(new Error('ECONNREFUSED'));
    await expect(promise).rejects.toThrow(/ECONNREFUSED/);
  });

  it('rejects on validation: missing agentId/text', async () => {
    const client = makeClient();
    await expect(client.sendTurn({ agentId: '', text: 'x' })).rejects.toThrow(/agentId/);
    await expect(client.sendTurn({ agentId: 'a', text: '' })).rejects.toThrow(/text/);
  });

  it('honours AbortSignal by closing the WS', async () => {
    const client = makeClient();
    const ac = new AbortController();
    const promise = client.sendTurn({ agentId: 'ag', text: 'x' }, ac.signal);
    const fake = FakeWebSocket.instances[0];
    fake.open();
    await Promise.resolve();
    ac.abort();
    fake.close(4000);
    await expect(promise).rejects.toBeDefined();
    expect(fake.closeCode).toBe(4000);
  });

  it('ignores unknown frame types and only resolves on done', async () => {
    const client = makeClient();
    const promise = client.sendTurn({ agentId: 'ag', text: 'hi' });
    const fake = FakeWebSocket.instances[0];
    fake.open();
    await Promise.resolve();
    fake.receive({ type: 'turn_status', active: true });
    fake.receive({ type: 'pong' });
    fake.receive({ type: 'chunk', delta: 'ok' });
    fake.receive({ type: 'done' });
    const result = await promise;
    expect(result.text).toBe('ok');
  });
});
