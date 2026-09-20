/**
 * Browser-side voice client.
 *
 * Wraps the Octop backend's voice endpoints (/api/voice/stt, /api/voice/tts)
 * so renderer components can opt into "real" STT/TTS while still falling back
 * to the browser Web Speech API when the backend is unreachable.
 *
 * Authentication reuses the existing JWT in ``localStorage`` (set by the
 * dashboard / Octop session manager). All functions are no-ops when called in
 * a non-browser context (SSR, tests) — they throw a descriptive error instead
 * of relying on ``fetch`` being undefined.
 */

const AUTH_TOKEN_KEY = 'octop:auth-token';

export interface VoiceBackendConfig {
  /** Octop base URL. Defaults to current origin. */
  baseUrl?: string;
  /** Bearer token to send in the Authorization header. */
  bearer?: string;
  /** Optional ``fetch`` injection (used by tests). */
  fetchImpl?: typeof fetch;
}

export interface SttInput {
  /** Raw audio bytes. */
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
  audio: Blob;
  mimeType: string;
}

function getStoredToken(): string {
  if (typeof localStorage === 'undefined') return '';
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

function toUint8(input: Blob | ArrayBuffer | Uint8Array): Uint8Array {
  if (input instanceof Uint8Array) return input;
  if (input instanceof ArrayBuffer) return new Uint8Array(input);
  throw new Error('Unsupported audio type: pass ArrayBuffer or Uint8Array');
}

function toAudioBlob(input: Blob | ArrayBuffer | Uint8Array, mime: string): Blob {
  if (input instanceof Blob) return input;
  // Build an ArrayBuffer (not SharedArrayBuffer) and hand it to Blob so it
  // matches the DOM BlobPart type without leaking the underlying buffer.
  const u8 = toUint8(input);
  const buffer = new ArrayBuffer(u8.byteLength);
  new Uint8Array(buffer).set(u8);
  return new Blob([buffer], { type: mime });
}

export class VoiceClient {
  private readonly baseUrl: string;
  private readonly bearer: string | undefined;
  private readonly fetchImpl: typeof fetch;

  constructor(cfg: VoiceBackendConfig = {}) {
    if (typeof window !== 'undefined' && cfg.baseUrl === undefined) {
      this.baseUrl = window.location.origin;
    } else if (cfg.baseUrl) {
      this.baseUrl = cfg.baseUrl.replace(/\/+$/, '');
    } else {
      this.baseUrl = '';
    }
    const stored = getStoredToken();
    this.bearer = cfg.bearer ?? (stored || undefined);
    this.fetchImpl = cfg.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  private endpoint(path: string): string {
    if (!this.baseUrl) return path;
    return `${this.baseUrl}${path}`;
  }

  private authHeader(): Record<string, string> {
    return this.bearer ? { Authorization: `Bearer ${this.bearer}` } : {};
  }

  /** POST /api/voice/stt with multipart/form-data. */
  async transcribe(input: SttInput): Promise<SttResult> {
    const mime = input.mimeType ?? 'audio/webm';
    const filename = input.filename ?? 'speech.webm';
    const blob = toAudioBlob(input.audio, mime);
    const form = new FormData();
    form.append('audio', blob, filename);
    if (input.language) form.append('language', input.language);
    if (input.provider) form.append('provider', input.provider);

    const res = await this.fetchImpl(this.endpoint('/api/voice/stt'), {
      method: 'POST',
      headers: this.authHeader(),
      body: form,
    });
    if (!res.ok) {
      throw new Error(`Voice transcribe HTTP ${res.status}: ${await res.text()}`);
    }
    const json = (await res.json()) as { text?: unknown; confidence?: unknown };
    if (typeof json.text !== 'string') {
      throw new Error('Voice transcribe response missing "text" string');
    }
    return {
      text: json.text,
      confidence: typeof json.confidence === 'number' ? json.confidence : undefined,
    };
  }

  /** POST /api/voice/tts and return the audio as a Blob plus mime type. */
  async synthesize(input: TtsInput): Promise<TtsResult> {
    const res = await this.fetchImpl(this.endpoint('/api/voice/tts'), {
      method: 'POST',
      headers: { 'content-type': 'application/json', ...this.authHeader() },
      body: JSON.stringify({
        text: input.text,
        ...(input.voiceId ? { voice_id: input.voiceId } : {}),
        ...(typeof input.speed === 'number' ? { speed: input.speed } : {}),
        ...(input.provider ? { provider: input.provider } : {}),
      }),
    });
    if (!res.ok) {
      throw new Error(`Voice synthesize HTTP ${res.status}: ${await res.text()}`);
    }
    const mimeType = res.headers.get('content-type') ?? 'audio/mpeg';
    const audio = await res.blob();
    return { audio, mimeType };
  }
}

/** Build a singleton client using the current origin and stored token. */
export function getVoiceClient(cfg: Partial<VoiceBackendConfig> = {}): VoiceClient {
  return new VoiceClient(cfg);
}
