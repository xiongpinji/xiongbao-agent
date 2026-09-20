/**
 * OctopVoiceClient
 *
 * Tiny HTTP client that bridges the Electron main process to Octop's
 * voice endpoints. Mirrors the minimal style of ``OctopBackendSseClient`` so
 * the renderer never needs to know about Octop URLs or auth headers.
 *
 *   POST /api/voice/stt  multipart/form-data { audio, language?, provider? }
 *     → { text: string, confidence?: number }
 *
 *   POST /api/voice/tts  application/json { text, voice_id?, speed?, provider? }
 *     → audio/* stream
 *
 * Both endpoints require an authenticated user; the caller supplies a bearer
 * token (the same one used for /api/tasks). The class is intentionally
 * dependency-free and unit-testable with ``fetchImpl``.
 */

export interface OctopVoiceClientOptions {
  baseUrl: string;
  bearer?: string;
  fetchImpl?: typeof fetch;
}

export interface SttInput {
  audio: Blob | ArrayBuffer | Uint8Array;
  mimeType?: string;
  filename?: string;
  language?: string;
  provider?: string;
}

export interface SttResult {
  text: string;
  confidence?: number;
}

export interface TtsInput {
  text: string;
  voiceId?: string;
  speed?: number;
  provider?: string;
}

export interface TtsResult {
  audio: ArrayBuffer;
  mimeType: string;
}

function toUint8(input: Blob | ArrayBuffer | Uint8Array): Uint8Array {
  if (input instanceof Uint8Array) return input;
  if (input instanceof ArrayBuffer) return new Uint8Array(input);
  // Blob fallback - read into buffer.
  // Synchronous blob access is not available; callers should pass ArrayBuffer
  // or Uint8Array. Throw with a useful message if they passed a Blob.
  throw new Error(
    'OctopVoiceClient: synchronous Blob conversion is not supported; pass ArrayBuffer/Uint8Array',
  );
}

export class OctopVoiceClient {
  private readonly baseUrl: string;
  private readonly bearer: string | undefined;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: OctopVoiceClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, '');
    this.bearer = opts.bearer;
    this.fetchImpl = opts.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  private authHeader(): Record<string, string> {
    return this.bearer ? { authorization: this.bearer } : {};
  }

  /**
   * Transcribe audio via Octop's /api/voice/stt endpoint.
   */
  async transcribe(input: SttInput): Promise<SttResult> {
    const bytes = toUint8(input.audio);
    const mime = input.mimeType ?? 'audio/webm';
    const filename = input.filename ?? 'speech.webm';
    const form = new FormData();
    // The platform FormData accepts a Blob; node 18+ exposes the File global.
    // Copy the bytes into a fresh ArrayBuffer so the Blob constructor receives
    // a BlobPart it accepts across lib.dom and node typings.
    const buffer = new ArrayBuffer(bytes.byteLength);
    new Uint8Array(buffer).set(bytes);
    const blob = new Blob([buffer], { type: mime });
    form.append('audio', blob, filename);
    if (input.language) form.append('language', input.language);
    if (input.provider) form.append('provider', input.provider);

    const res = await this.fetchImpl(`${this.baseUrl}/api/voice/stt`, {
      method: 'POST',
      headers: this.authHeader(),
      body: form,
    });
    if (!res.ok) {
      throw new Error(`Octop transcribe HTTP ${res.status}: ${await res.text()}`);
    }
    const json = (await res.json()) as { text?: unknown; confidence?: unknown };
    if (typeof json.text !== 'string') {
      throw new Error('Octop transcribe response missing "text" string');
    }
    return {
      text: json.text,
      confidence: typeof json.confidence === 'number' ? json.confidence : undefined,
    };
  }

  /**
   * Synthesize speech via Octop's /api/voice/tts endpoint and return the raw
   * audio bytes plus the announced content type.
   */
  async synthesize(input: TtsInput): Promise<TtsResult> {
    const body = {
      text: input.text,
      ...(input.voiceId ? { voice_id: input.voiceId } : {}),
      ...(typeof input.speed === 'number' ? { speed: input.speed } : {}),
      ...(input.provider ? { provider: input.provider } : {}),
    };
    const res = await this.fetchImpl(`${this.baseUrl}/api/voice/tts`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...this.authHeader() },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      throw new Error(`Octop synthesize HTTP ${res.status}: ${await res.text()}`);
    }
    const mimeType = res.headers.get('content-type') ?? 'audio/mpeg';
    const audio = await res.arrayBuffer();
    return { audio, mimeType };
  }
}
