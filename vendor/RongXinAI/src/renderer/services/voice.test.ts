// @vitest-environment node
import { describe, it, expect, vi } from 'vitest';
import { VoiceClient } from './voice';

describe('VoiceClient', () => {
  function makeResponse(status: number, body: any, contentType = 'application/json') {
    if (body instanceof ArrayBuffer) {
      return new Response(body, { status, headers: { 'content-type': contentType } });
    }
    if (body instanceof Blob) {
      return new Response(body, { status, headers: { 'content-type': contentType } });
    }
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': contentType },
    });
  }

  // Helper: wrap a vi.fn so it satisfies the strict `typeof fetch` signature.
  function fakeFetch(impl: (input: any, init?: RequestInit) => Promise<Response>): typeof fetch {
    return vi.fn(impl) as unknown as typeof fetch;
  }

  it('transcribe attaches multipart body and Authorization header', async () => {
    const seen: { headers?: Record<string, string>; body?: any } = {};
    const fetchImpl = fakeFetch(async (_url, init) => {
      seen.headers = init?.headers as Record<string, string>;
      seen.body = init?.body;
      return makeResponse(200, { text: '你好', confidence: 0.91 });
    });
    const c = new VoiceClient({
      baseUrl: 'https://octop.test',
      bearer: 'jwt-1',
      fetchImpl,
    });
    const out = await c.transcribe({
      audio: new Uint8Array([1, 2, 3, 4]),
      mimeType: 'audio/wav',
      filename: 'speech.wav',
      language: 'zh-CN',
      provider: 'mimo',
    });
    expect(out).toEqual({ text: '你好', confidence: 0.91 });
    expect(seen.headers?.Authorization).toBe('Bearer jwt-1');
    expect(seen.body).toBeInstanceOf(FormData);
  });

  it('transcribe throws on non-OK', async () => {
    const fetchImpl = fakeFetch(async () => makeResponse(500, 'boom'));
    const c = new VoiceClient({ baseUrl: 'https://x.test', fetchImpl });
    await expect(c.transcribe({ audio: new Uint8Array([1]) })).rejects.toThrow(/HTTP 500/);
  });

  it('transcribe throws if "text" missing', async () => {
    const fetchImpl = fakeFetch(async () => makeResponse(200, { confidence: 0.5 }));
    const c = new VoiceClient({ baseUrl: 'https://x.test', fetchImpl });
    await expect(c.transcribe({ audio: new Uint8Array([1]) })).rejects.toThrow(/missing "text"/);
  });

  it('synthesize returns Blob with declared mime type', async () => {
    const seen: { headers?: Record<string, string>; body?: string } = {};
    const fetchImpl = fakeFetch(async (_url, init) => {
      seen.headers = init?.headers as Record<string, string>;
      seen.body = typeof init?.body === 'string' ? init.body : '';
      return makeResponse(200, new Uint8Array([0xff, 0xfb, 0x90]).buffer, 'audio/mpeg');
    });
    const c = new VoiceClient({ baseUrl: 'https://x.test', bearer: 'jwt-2', fetchImpl });
    const out = await c.synthesize({ text: '你好', voiceId: 'female', speed: 1.05 });
    expect(out.mimeType).toBe('audio/mpeg');
    expect(out.audio).toBeInstanceOf(Blob);
    expect(out.audio.size).toBe(3);
    expect(seen.headers?.Authorization).toBe('Bearer jwt-2');
    expect(JSON.parse(seen.body ?? '{}')).toEqual({
      text: '你好',
      voice_id: 'female',
      speed: 1.05,
    });
  });

  it('synthesize defaults mime to audio/mpeg when server omits it', async () => {
    const fetchImpl = fakeFetch(async () =>
      makeResponse(200, new ArrayBuffer(8), 'audio/mpeg'),
    );
    const c = new VoiceClient({ baseUrl: 'https://x.test', fetchImpl });
    const out = await c.synthesize({ text: 'hi' });
    expect(out.mimeType).toBe('audio/mpeg');
  });

  it('omits Authorization header when no token', async () => {
    const fetchImpl = fakeFetch(async () => makeResponse(200, { text: 'hi' }));
    const c = new VoiceClient({ baseUrl: 'https://x.test', fetchImpl });
    await c.transcribe({ audio: new Uint8Array([1]) });
    const calls = (fetchImpl as unknown as ReturnType<typeof vi.fn>).mock.calls;
    const init = calls[0]?.[1] as RequestInit | undefined;
    expect((init?.headers as Record<string, string> | undefined)?.Authorization).toBeUndefined();
  });

  it('uses provided baseUrl for both endpoints', async () => {
    const seenUrls: string[] = [];
    const fetchImpl = fakeFetch(async (input: any) => {
      const url = String(input);
      seenUrls.push(url);
      return url.includes('/stt')
        ? makeResponse(200, { text: 'hi' })
        : makeResponse(200, new ArrayBuffer(4), 'audio/mpeg');
    });
    const c = new VoiceClient({ baseUrl: 'https://api.example.com', fetchImpl });
    await c.transcribe({ audio: new Uint8Array([1]) });
    await c.synthesize({ text: 'hi' });
    expect(seenUrls[0]).toBe('https://api.example.com/api/voice/stt');
    expect(seenUrls[1]).toBe('https://api.example.com/api/voice/tts');
  });
});
