// @vitest-environment node
import { describe, it, expect, vi } from 'vitest';
import {
  OctopBackendSseClient,
  parseSseBuffer,
  type OctopSseEvent,
} from './OctopBackendSseClient';

describe('parseSseBuffer', () => {
  it('parses one frame', () => {
    const frame = `id: 1\nevent: message\ndata: {"kind":"message","text":"hi"}\n\n`;
    const { events, remainder } = parseSseBuffer(frame);
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({
      id: 1,
      event: 'message',
      data: { kind: 'message', text: 'hi' },
    });
    expect(remainder).toBe('');
  });

  it('parses multiple frames and keeps trailing partial', () => {
    const frames = [
      'id: 1',
      'event: message',
      'data: {"a":1}',
      '',
      '',
      'id: 2',
      'event: tool',
      'data: {"a":2}',
      '',
      'id: 3',
    ].join('\n');
    const { events, remainder } = parseSseBuffer(frames);
    expect(events).toHaveLength(2);
    expect(events[0]?.id).toBe(1);
    expect(events[1]?.id).toBe(2);
    expect(remainder).toBe('id: 3');
  });

  it('skips comment-only heartbeats', () => {
    const frame = ': ping\n\nid: 5\nevent: message\ndata: {"x":1}\n\n';
    const { events } = parseSseBuffer(frame);
    expect(events).toHaveLength(1);
    expect(events[0]?.id).toBe(5);
  });

  it('marks terminal events', () => {
    const buf = `id: 1\nevent: done\ndata: {"ok":true}\n\n`;
    const { events } = parseSseBuffer(buf);
    expect(events[0]?.terminal).toBe(true);
  });

  it('marks data.terminal === true', () => {
    const buf = `id: 1\nevent: progress\ndata: {"terminal":true,"reason":"complete"}\n\n`;
    const { events } = parseSseBuffer(buf);
    expect(events[0]?.terminal).toBe(true);
  });

  it('preserves non-JSON data as a string', () => {
    const buf = `event: log\ndata: plain text here\n\n`;
    const { events } = parseSseBuffer(buf);
    expect(events[0]?.data).toBe('plain text here');
  });
});

describe('OctopBackendSseClient', () => {
  function sseResponse(events: OctopSseEvent[]): Response {
    const chunks = events
      .map((e) => `id: ${e.id}\nevent: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`)
      .join('');
    return new Response(chunks, {
      headers: { 'content-type': 'text/event-stream; charset=utf-8' },
      status: 200,
    });
  }

  it('startTask POSTs and returns taskId', async () => {
    const fetchImpl = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const req = url as string;
      if (req.endsWith('/api/tasks') && init?.method === 'POST') {
        return new Response(JSON.stringify({ task_id: 'abc-123' }), { status: 201 });
      }
      return new Response('not found', { status: 404 });
    });
    const c = new OctopBackendSseClient({ baseUrl: 'http://octop.local:8088', fetchImpl });
    const out = await c.startTask({ prompt: 'hi' });
    expect(out.taskId).toBe('abc-123');
  });

  it('streamTaskEvents yields frames and stops at terminal', async () => {
    const events: OctopSseEvent[] = [
      { id: 1, event: 'message', data: { text: 'hello' }, terminal: false },
      { id: 2, event: 'tool_call', data: { tool: 'bash' }, terminal: false },
      { id: 3, event: 'done', data: { ok: true }, terminal: true },
    ];
    const c = new OctopBackendSseClient({
      baseUrl: 'http://octop.local:8088',
      fetchImpl: vi.fn(async () => sseResponse(events)),
    });
    const collected: OctopSseEvent[] = [];
    for await (const ev of c.streamTaskEvents('task-1')) {
      collected.push(ev);
    }
    expect(collected).toHaveLength(3);
    expect(collected[2]?.terminal).toBe(true);
  });

  it('attaches bearer token when provided', async () => {
    const seenHeaders: Record<string, string> = {};
    const fetchImpl = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      Object.assign(seenHeaders, init?.headers as Record<string, string>);
      return new Response('id: 1\nevent: done\ndata: {}\n\n', {
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
      });
    });
    const c = new OctopBackendSseClient({
      baseUrl: 'http://octop.local',
      bearer: 'Bearer t-1',
      fetchImpl,
    });
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    for await (const _ of c.streamTaskEvents('t')) { /* drain */ }
    expect(seenHeaders.authorization).toBe('Bearer t-1');
  });

  it('throws on non-OK startTask', async () => {
    const fetchImpl = vi.fn(async () => new Response('boom', { status: 500 }));
    const c = new OctopBackendSseClient({ baseUrl: 'http://octop.local', fetchImpl });
    await expect(c.startTask({ prompt: 'x' })).rejects.toThrow(/HTTP 500/);
  });
});
