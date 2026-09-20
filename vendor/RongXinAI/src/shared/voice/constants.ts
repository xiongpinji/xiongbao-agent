/**
 * Centralized IPC channel names for the voice bridge between the Electron
 * renderer and the Octop backend. Handlers live in the main process; the
 * renderer only references these constants.
 */

export const VoiceIpcChannel = {
  Stt: 'voice:stt',
  Tts: 'voice:tts',
  GetConfig: 'voice:getConfig',
} as const;
export type VoiceIpcChannel = (typeof VoiceIpcChannel)[keyof typeof VoiceIpcChannel];

export interface VoiceBridgeSttRequest {
  /** Base64-encoded audio payload (any format Octop /api/voice/stt accepts). */
  audioBase64: string;
  mimeType: string;
  filename?: string;
  language?: string;
  provider?: string;
}

export interface VoiceBridgeSttResponse {
  text: string;
  confidence?: number;
}

export interface VoiceBridgeTtsRequest {
  text: string;
  voiceId?: string;
  speed?: number;
  provider?: string;
}

export interface VoiceBridgeTtsResponse {
  /** Base64-encoded audio payload; decode to feed into <audio src> or save. */
  audioBase64: string;
  mimeType: string;
}

export interface VoiceBridgeConfig {
  baseUrl?: string;
  hasAuth: boolean;
}
