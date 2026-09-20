// @vitest-environment node
import { describe, it, expect, vi } from 'vitest';
import { OctopVoiceClient } from './OctopVoiceClient';

describe('OctopVoiceClient', () => {
  it('transcribe POSTs multipart form and returns text/confidence', async () => {
    const seen: { url?: string; method?: string; headers?: Record<string, string>; body?: any } = {};
    const fetchImpl = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      seen.url = String(url);
      seen.method = init?.method;
      seen.headers = init?.headers as Record<string, string>;
      seen.body = init?.body;
      return new Response(JSON.stringify({ text: '你好', confidence: 0.92 }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    });
    const c = new OctopVoiceClient({ baseUrl: 'http://octop.local:8088', fetchImpl });
    const out = await c.transcribe({
      audio: new Uint8Array([1, 2, 3, 4]),
      mimeType: 'audio/wav',
      filename: 'speech.wav',
      language: 'zh-CN',
      provider: 'mimo',
    });
    expect(out).toEqual({ text: '你好', confidence: 0.92 });
    expect(seen.url).toBe('http://octop.local:8088/api/voice/stt');
    expect(seen.method).toBe('POST');
    expect(seen.body).toBeInstanceOf(FormData);
  });

  it('transcribe throws on non-OK response', async () => {
    const fetchImpl = vi.fn(async () => new Response('boom', { status: 500 }));
    const c = new OctopVoiceClient({ baseUrl: 'http://octop.local', fetchImpl });
    await expect(
      c.transcribe({ audio: new Uint8Array([1]) }),
    ).rejects.toThrow(/HTTP 500/);
  });

  it('transcribe throws if response lacks "text" string', async () => {
    const fetchImpl = vi.fn(
      async () => new Response(JSON.stringify({ confidence: 0.5 }), { status: 200 }),
    );
    const c = new OctopVoiceClient({ baseUrl: 'http://octop.local', fetchImpl });
    await expect(
      c.transcribe({ audio: new Uint8Array([1]) }),
    ).rejects.toThrow(/missing "text"/);
  });

  it('synthesize POSTs JSON and returns ArrayBuffer + mime type', async () => {
    const bytes = new Uint8Array([0xff, 0xfb, 0x90, 0x44]); // arbitrary MP3 frame header
    const seen: { headers?: Record<string, string>; body?: string } = {};
    const fetchImpl = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      seen.headers = init?.headers as Record<string, string>;
      seen.body = typeof init?.body === 'string' ? init.body : '';
      return new Response(bytes, {
        status: 200,
        headers: { 'content-type': 'audio/mpeg' },
      });
    });
    const c = new OctopVoiceClient({
      baseUrl: 'http://octop.local:8088',
      bearer: 'Bearer t-1',
      fetchImpl,
    });
    const out = await c.synthesize({ text: '你好，世界', voiceId: 'female', speed: 1.1 });
    expect(out.mimeType).toBe('audio/mpeg');
    expect(out.audio.byteLength).toBe(4);
    expect(new Uint8Array(out.audio)).toEqual(bytes);
    expect(seen.headers?.authorization).toBe('Bearer t-1');
    expect(seen.headers?.['content-type']).toBe('application/json');
    expect(JSON.parse(seen.body ?? '{}')).toEqual({
      text: '你好，世界',
      voice_id: 'female',
      speed: 1.1,
    });
  });

  it('synthesize throws on non-OK response', async () => {
    const fetchImpl = vi.fn(async () => new Response('oops', { status: 502 }));
    const c = new OctopVoiceClient({ baseUrl: 'http://octop.local', fetchImpl });
    await expect(c.synthesize({ text: 'hi' })).rejects.toThrow(/HTTP 502/);
  });

  it('synthesize defaults mime to audio/mpeg when server omits it', async () => {
    const fetchImpl = vi.fn(
      async () => new Response(new Uint8Array([1]), { status: 200 }),
    );
    const c = new OctopVoiceClient({ baseUrl: 'http://octop.local', fetchImpl });
    const out = await c.synthesize({ text: 'hi' });
    expect(out.mimeType).toBe('audio/mpeg');
  });
});
