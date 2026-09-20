/**
 * Unit tests for OctopChatHandler — verifies the IM-side contract is
 * preserved while delegating to OctopChatClient.
 */

import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { OctopChatHandler } from './OctopChatHandler';
import type { IMMessage, IMSettings } from './types';
import type { OctopChatClientOptions } from '../libs/octopBridge/OctopChatClient';

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  headers: Record<string, string>;
  sentFrames: string[] = [];
  private listeners = new Map<string, ((...args: unknown[]) => void)[]>();

  constructor(url: string, opts?: { headers?: Record<string, string> }) {
    this.url = url;
    this.headers = opts?.headers ?? {};
    FakeWebSocket.instances.push(this);
  }
  on(event: string, listener: (...args: unknown[]) => void): this {
    const arr = this.listeners.get(event) ?? [];
    arr.push(listener);
    this.listeners.set(event, arr);
    return this;
  }
  once(event: string, listener: (...args: unknown[]) => void): this {
    const wrap = (...args: unknown[]): void => {
      const remaining = (this.listeners.get(event) ?? []).filter(l => l !== wrap);
      this.listeners.set(event, remaining);
      listener(...args);
    };
    return this.on(event, wrap);
  }
  send(frame: string): void {
    this.sentFrames.push(frame);
  }
  close(): void {
    this.emit('close', 1000);
  }
  emit(event: string, ...args: unknown[]): void {
    for (const l of [...(this.listeners.get(event) ?? [])]) l(...args);
  }
  open(): void {
    this.emit('open');
  }
  receive(payload: unknown): void {
    const text = typeof payload === 'string' ? payload : JSON.stringify(payload);
    this.emit('message', Buffer.from(text));
  }
}

const imSettings = (overrides: Partial<IMSettings> = {}): IMSettings => ({
  systemPrompt: 'You are helpful.',
  skillsEnabled: false,
  ...overrides,
});

const imMessage = (overrides: Partial<IMMessage> = {}): IMMessage => ({
  id: 'm-1',
  platform: 'feishu',
  chatId: 'chat-1',
  senderId: 'user-1',
  content: 'hi there',
  timestamp: Date.now(),
  ...overrides,
});

function makeHandler(opts: {
  getAgentId?: () => string | null;
  getSkillsPrompt?: () => Promise<string | null>;
  imSettings?: IMSettings;
  bearer?: string;
}) {
  const Ctor = FakeWebSocket as unknown as NonNullable<OctopChatClientOptions['WebSocketCtor']>;
  return new OctopChatHandler({
    baseUrl: 'http://octop.local',
    bearer: opts.bearer ?? 'jwt',
    getAgentId: opts.getAgentId ?? (() => 'ag-1'),
    imSettings: opts.imSettings ?? imSettings(),
    WebSocketCtor: Ctor,
    ...(opts.getSkillsPrompt ? { getSkillsPrompt: opts.getSkillsPrompt } : {}),
  });
}

describe('OctopChatHandler', () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
  });
  afterEach(() => {
    FakeWebSocket.instances = [];
  });

  it('forwards the user message to octop and returns the assistant reply', async () => {
    const handler = makeHandler({});
    const promise = handler.processMessage(imMessage({ content: 'ping' }));
    await Promise.resolve(); // let the handler reach sendTurn
    const fake = FakeWebSocket.instances[0];
    expect(fake).toBeDefined();
    fake.open();
    await Promise.resolve();
    fake.receive({ type: 'chunk', delta: 'pong' });
    fake.receive({ type: 'done' });
    const reply = await promise;
    expect(reply).toBe('pong');
    expect(fake.url).toContain('/api/agents/ag-1/chat/ws');
    expect(fake.headers.authorization).toBe('Bearer jwt');
    expect(fake.sentFrames).toHaveLength(1);
    const sent = JSON.parse(fake.sentFrames[0]) as Record<string, unknown>;
    expect(sent.type).toBe('user_turn');
    // The IM-side handler always appends the media instruction; the user
    // content appears first.
    expect(String(sent.text)).toContain('ping');
    expect(String(sent.text)).toContain('<im_media_capabilities>');
  });

  it('appends the skills prompt and media instruction when enabled', async () => {
    const handler = makeHandler({
      imSettings: imSettings({ skillsEnabled: true }),
      getSkillsPrompt: async () => '<skills>math</skills>',
    });
    const promise = handler.processMessage(imMessage({ content: '2+2?' }));
    // Two microtasks: first await (getSkillsPrompt), then second await (sendTurn → new WS).
    await Promise.resolve();
    await Promise.resolve();
    const fake = FakeWebSocket.instances[0];
    expect(fake).toBeDefined();
    fake.open();
    await Promise.resolve();
    fake.receive({ type: 'chunk', delta: '4' });
    fake.receive({ type: 'done' });
    await promise;

    const sent = JSON.parse(fake.sentFrames[0]) as Record<string, unknown>;
    const text = String(sent.text);
    expect(text).toContain('2+2?');
    expect(text).toContain('<skills>math</skills>');
  });

  it('rejects when getAgentId returns empty', async () => {
    const handler = makeHandler({ getAgentId: () => null });
    await expect(handler.processMessage(imMessage())).rejects.toThrow(/getAgentId/);
  });

  it('rejects when octop reports an error', async () => {
    const handler = makeHandler({});
    const promise = handler.processMessage(imMessage());
    await Promise.resolve();
    const fake = FakeWebSocket.instances[0];
    expect(fake).toBeDefined();
    fake.open();
    await Promise.resolve();
    fake.receive({ type: 'error', message: 'agent offline' });
    await expect(promise).rejects.toThrow(/agent offline/);
  });
});
