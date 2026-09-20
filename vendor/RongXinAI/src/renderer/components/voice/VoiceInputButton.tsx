import { useCallback, useEffect, useRef, useState } from 'react';
import { Mic, MicOff, Volume2, AlertCircle, Loader2 } from 'lucide-react';
import { cn } from '@shared/lib/utils';
import { i18nService } from '../../services/i18n';
import type { VoiceClient } from '../../services/voice';

export type VoiceInputStatus = 'idle' | 'starting' | 'listening' | 'processing' | 'error';

export interface VoiceInputButtonProps {
  /** Called whenever interim or final transcript text updates */
  onTranscript?: (text: string, isFinal: boolean) => void;
  /** Called when user finalizes a phrase (mic auto-stops) */
  onFinalTranscript?: (text: string) => void;
  /** Called when recognition fails (e.g. permission denied). */
  onError?: (message: string) => void;
  /** Override language, defaults to zh-CN */
  lang?: string;
  /** Whether the button is disabled */
  disabled?: boolean;
  /** Size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Custom class */
  className?: string;
  /** Continuous mode (keep listening until user clicks stop) */
  continuous?: boolean;
  /** Auto-stop after silence (ms), default 3000 */
  silenceTimeoutMs?: number;
  /**
   * When provided, the component records audio via MediaRecorder and posts
   * it to the supplied VoiceClient instead of using Web Speech API. This is
   * how production builds wire up the Octop STT backend.
   */
  backend?: VoiceClient | null;
}

interface SpeechRecognitionLike {
  start: () => void;
  stop: () => void;
  abort: () => void;
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onresult: ((e: any) => void) | null;
  onerror: ((e: any) => void) | null;
  onend: (() => void) | null;
  onstart: (() => void) | null;
}

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === 'undefined') return null;
  const w = window as any;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

export function VoiceInputButton({
  onTranscript,
  onFinalTranscript,
  onError,
  lang = 'zh-CN',
  disabled = false,
  size = 'md',
  className,
  continuous = true,
  silenceTimeoutMs = 3000,
  backend,
}: VoiceInputButtonProps) {
  const [status, setStatus] = useState<VoiceInputStatus>('idle');
  const [transcript, setTranscript] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [supported, setSupported] = useState(true);

  // Localised copy. Lookups fall back to the key when a translation is
  // missing so the developer can still spot the gap.
  const localize = useCallback((key: string, fallback: string): string => {
    const value = i18nService.t(key);
    return value && value !== key ? value : fallback;
  }, []);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const silenceTimerRef = useRef<number | null>(null);
  const transcriptRef = useRef('');
  const restartRef = useRef(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaChunksRef = useRef<Blob[]>([]);

  function getMediaRecorderCtor(): typeof MediaRecorder | null {
    if (typeof window === 'undefined') return null;
    return (window as any).MediaRecorder || null;
  }

  const startBackend = useCallback(async () => {
    const MR = getMediaRecorderCtor();
    if (!MR) {
      setErrorMsg(localize('voiceInputUnsupported', '当前浏览器不支持语音识别'));
      setStatus('error');
      return;
    }
    try {
      setErrorMsg(null);
      setTranscript('');
      transcriptRef.current = '';
      setStatus('starting');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      const recorder = new MR(stream);
      mediaRecorderRef.current = recorder;
      mediaChunksRef.current = [];
      recorder.ondataavailable = (event: any) => {
        if (event.data && event.data.size > 0) {
          mediaChunksRef.current.push(event.data);
        }
      };
      recorder.onstop = async () => {
        try {
          const mime = recorder.mimeType || 'audio/webm';
          const blob = new Blob(mediaChunksRef.current, { type: mime });
          mediaChunksRef.current = [];
          stream.getTracks().forEach(t => t.stop());
          mediaStreamRef.current = null;
          mediaRecorderRef.current = null;
          setStatus('processing');
          const result = await backend!.transcribe({
            audio: blob,
            mimeType: mime,
            filename: `recording.${mime.includes('mp4') ? 'mp4' : 'webm'}`,
            language: lang,
          });
          const text = result.text?.trim();
          if (!text) {
            setErrorMsg(localize('voiceInputNoSpeech', '未检测到语音，请重试'));
            setStatus('error');
            return;
          }
          setTranscript(text);
          transcriptRef.current = text;
          onTranscript?.(text, true);
          onFinalTranscript?.(text);
          setStatus('idle');
        } catch (err) {
          setErrorMsg(
            localize('voiceInputError', `语音识别错误: ${(err as Error).message || 'unknown'}`),
          );
          setStatus('error');
        }
      };
      recorder.start();
      setStatus('listening');
    } catch (err) {
      setErrorMsg(
        localize('voiceInputError', `启动录音失败: ${(err as Error).message || 'unknown'}`),
      );
      setStatus('error');
      mediaStreamRef.current?.getTracks().forEach(t => t.stop());
      mediaStreamRef.current = null;
      mediaRecorderRef.current = null;
    }
  }, [backend, lang, localize, onFinalTranscript, onTranscript]);

  function stopBackend() {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        // ignore
      }
    } else {
      mediaStreamRef.current?.getTracks().forEach(t => t.stop());
      mediaStreamRef.current = null;
    }
  }

  useEffect(() => {
    if (status === 'error' && errorMsg) onError?.(errorMsg);
  }, [status, errorMsg, onError]);

  useEffect(() => {
    const SR = getSpeechRecognition();
    setSupported(!!SR);
    return () => {
      recognitionRef.current?.abort();
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
      }
    };
  }, []);

  const resetSilenceTimer = useCallback(() => {
    if (silenceTimerRef.current) clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = window.setTimeout(() => {
      if (recognitionRef.current && continuous) {
        recognitionRef.current.stop();
      }
    }, silenceTimeoutMs);
  }, [continuous, silenceTimeoutMs]);

  const start = useCallback(() => {
    const SR = getSpeechRecognition();
    if (!SR) {
      setSupported(false);
      setErrorMsg(localize('voiceInputUnsupported', '当前浏览器不支持语音识别'));
      setStatus('error');
      return;
    }

    setErrorMsg(null);
    setTranscript('');
    transcriptRef.current = '';
    setStatus('starting');

    try {
      const recognition = new SR();
      recognition.continuous = continuous;
      recognition.interimResults = true;
      recognition.lang = lang;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setStatus('listening');
      };

      recognition.onresult = (event: any) => {
        let interim = '';
        let final = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          if (result.isFinal) {
            final += result[0].transcript;
          } else {
            interim += result[0].transcript;
          }
        }
        const merged = (transcriptRef.current + final + interim).trim();
        setTranscript(merged);
        onTranscript?.(merged, !!final);
        if (final) {
          transcriptRef.current = (transcriptRef.current + final).trim();
          onFinalTranscript?.(transcriptRef.current);
        }
        if (continuous) resetSilenceTimer();
      };

      recognition.onerror = (event: any) => {
        if (event.error === 'no-speech') {
          setErrorMsg(localize('voiceInputNoSpeech', '未检测到语音，请重试'));
        } else if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
          setErrorMsg(localize('voiceInputNotAllowed', '请允许麦克风权限'));
        } else if (event.error === 'network') {
          setErrorMsg(localize('voiceInputNetworkError', '网络错误，语音识别不可用'));
        } else {
          setErrorMsg(localize('voiceInputError', `语音识别错误: ${event.error}`));
        }
        setStatus('error');
      };

      recognition.onend = () => {
        if (status === 'listening' && restartRef.current && continuous) {
          try {
            recognition.start();
          } catch {
            setStatus('idle');
          }
        } else {
          setStatus('idle');
          if (transcriptRef.current) {
            onFinalTranscript?.(transcriptRef.current);
          }
        }
      };

      recognitionRef.current = recognition;
      restartRef.current = true;
      recognition.start();
      if (continuous) resetSilenceTimer();
    } catch {
      setErrorMsg(localize('voiceInputStartFailed', '启动语音识别失败'));
      setStatus('error');
    }
  }, [continuous, lang, localize, onFinalTranscript, onTranscript, resetSilenceTimer, status]);

  const stop = useCallback(() => {
    restartRef.current = false;
    if (backend) {
      stopBackend();
    } else {
      recognitionRef.current?.stop();
    }
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
  }, [backend]);

  const toggle = useCallback(() => {
    if (status === 'idle' || status === 'error') {
      if (backend) {
        void startBackend();
      } else {
        start();
      }
    } else {
      stop();
    }
  }, [backend, start, startBackend, status, stop]);

  const isActive = status === 'listening' || status === 'starting';

  const sizeMap = {
    sm: { btn: 'size-8', icon: 'size-4' },
    md: { btn: 'size-10', icon: 'size-5' },
    lg: { btn: 'size-12', icon: 'size-6' },
  } as const;
  const sz = sizeMap[size];

  if (!supported) {
    return (
      <button
        type="button"
        disabled
        title={localize('voiceInputUnsupported', '浏览器不支持语音识别')}
        className={cn(
          'flex shrink-0 items-center justify-center rounded-full text-muted-foreground/40',
          sz.btn,
          className,
        )}
      >
        <MicOff className={sz.icon} />
      </button>
    );
  }

  return (
    <div className="relative flex shrink-0 items-center">
      <button
        type="button"
        onClick={toggle}
        disabled={disabled}
        title={
          isActive
            ? localize('voiceInputStop', '点击停止录音')
            : status === 'processing'
              ? localize('voiceInputProcessing', '正在处理')
              : localize('voiceInputStart', '点击开始语音输入')
        }
        className={cn(
          'flex shrink-0 items-center justify-center rounded-full border transition-all',
          sz.btn,
          isActive
            ? 'border-(--zy-primary) bg-(--zy-primary-muted) text-(--zy-primary)'
            : status === 'error'
              ? 'border-(--zy-destructive) bg-(--zy-destructive)/10 text-(--zy-destructive)'
              : 'border-border bg-background text-muted-foreground hover:border-(--zy-primary) hover:bg-(--zy-primary-muted) hover:text-(--zy-primary)',
          disabled && 'cursor-not-allowed opacity-40',
          isActive && 'animate-pulse ring-2 ring-(--zy-primary-muted)',
          className,
        )}
      >
        {status === 'starting' || status === 'processing' ? (
          <Loader2 className={cn(sz.icon, 'animate-spin')} />
        ) : isActive ? (
          <Volume2 className={sz.icon} />
        ) : status === 'error' ? (
          <AlertCircle className={sz.icon} />
        ) : (
          <Mic className={sz.icon} />
        )}
      </button>

      {isActive && (
        <span className="pointer-events-none absolute -right-1 -top-1 flex size-3">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-(--zy-voice-recording) opacity-75" />
          <span className="relative inline-flex size-3 rounded-full bg-(--zy-voice-recording)" />
        </span>
      )}
      {/* Use transcript state so re-renders stay in sync; visually hidden when empty. */}
      <span className="sr-only" aria-live="polite">{transcript}</span>

      {status === 'error' && errorMsg && (
        <div className="pointer-events-none absolute left-full top-1/2 z-50 ml-2 -translate-y-1/2 whitespace-nowrap rounded-md bg-(--zy-destructive) px-2 py-1 text-xs text-(--zy-destructive-foreground) shadow-lg">
          {errorMsg}
        </div>
      )}
    </div>
  );
}

export default VoiceInputButton;
