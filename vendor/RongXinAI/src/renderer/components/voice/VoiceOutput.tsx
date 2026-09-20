import { useEffect, useRef, useState } from 'react';
import { i18nService } from '../../services/i18n';
import type { VoiceClient } from '../../services/voice';
import { Volume2, Play, Pause, Square, Settings2 } from 'lucide-react';
import { cn } from '@shared/lib/utils';

export interface VoiceOutputProps {
  text: string;
  lang?: string;
  className?: string;
  /** Auto-play on mount */
  autoPlay?: boolean;
  /** Show rate / pitch controls */
  showControls?: boolean;
  /**
   * When provided, the component posts ``text`` to the Octop TTS endpoint
   * via the supplied client and plays the returned audio through an
   * HTMLAudioElement instead of using window.speechSynthesis.
   */
  backend?: VoiceClient | null;
}

interface SpeechSynthesisUtteranceConfig {
  rate: number;
  pitch: number;
  volume: number;
  voice?: SpeechSynthesisVoice;
}

export function VoiceOutput({
  text,
  lang = 'zh-CN',
  className,
  autoPlay = false,
  showControls = false,
  backend,
}: VoiceOutputProps) {
  const { t } = { t: (key: string) => i18nService.t(key) };
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [config, setConfig] = useState<SpeechSynthesisUtteranceConfig>({
    rate: 1.0,
    pitch: 1.0,
    volume: 1.0,
  });
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const lastUrlRef = useRef<string | null>(null);

  const useBackend = !!backend;
  const supported = useBackend
    ? typeof window !== 'undefined' && typeof window.Audio !== 'undefined'
    : typeof window !== 'undefined' && 'speechSynthesis' in window;

  function cleanupAudio() {
    if (lastUrlRef.current) {
      URL.revokeObjectURL(lastUrlRef.current);
      lastUrlRef.current = null;
    }
    audioRef.current = null;
  }

  async function speakBackend() {
    if (!backend || !text) return;
    try {
      const out = await backend.synthesize({ text, speed: config.rate });
      if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current);
      const url = URL.createObjectURL(out.audio);
      lastUrlRef.current = url;
      const audio = new Audio(url);
      audio.playbackRate = config.rate;
      audioRef.current = audio;
      audio.onplay = () => {
        setIsSpeaking(true);
        setIsPaused(false);
      };
      audio.onended = () => {
        setIsSpeaking(false);
        setIsPaused(false);
        cleanupAudio();
      };
      audio.onerror = () => {
        setIsSpeaking(false);
        setIsPaused(false);
        cleanupAudio();
      };
      audio.onpause = () => setIsPaused(true);
      await audio.play();
    } catch {
      setIsSpeaking(false);
      setIsPaused(false);
      cleanupAudio();
    }
  }

  function speakBrowser() {
    if (!supported || !text) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = lang;
    utter.rate = config.rate;
    utter.pitch = config.pitch;
    utter.volume = config.volume;
    if (config.voice) utter.voice = config.voice;

    utter.onstart = () => {
      setIsSpeaking(true);
      setIsPaused(false);
    };
    utter.onend = () => {
      setIsSpeaking(false);
      setIsPaused(false);
    };
    utter.onerror = () => {
      setIsSpeaking(false);
      setIsPaused(false);
    };
    utter.onpause = () => setIsPaused(true);
    utter.onresume = () => setIsPaused(false);

    window.speechSynthesis.speak(utter);
  }

  function speak() {
    if (useBackend) {
      void speakBackend();
    } else {
      speakBrowser();
    }
  }

  function pause() {
    if (useBackend) {
      const audio = audioRef.current;
      if (!audio) return;
      if (audio.paused) {
        void audio.play();
      } else {
        audio.pause();
      }
      return;
    }
    if (!supported) return;
    if (isPaused) {
      window.speechSynthesis.resume();
    } else {
      window.speechSynthesis.pause();
    }
  }

  function stop() {
    if (useBackend) {
      const audio = audioRef.current;
      if (audio) {
        audio.pause();
        audio.currentTime = 0;
      }
      setIsSpeaking(false);
      setIsPaused(false);
      cleanupAudio();
      return;
    }
    if (!supported) return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
    setIsPaused(false);
  }

  useEffect(() => {
    if (autoPlay && text && !isSpeaking) {
      speak();
    }
    return () => {
      if (useBackend) {
        cleanupAudio();
      } else if (supported && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, autoPlay]);

  if (!supported) return null;

  return (
    <div className={cn('inline-flex items-center gap-1', className)}>
      {!isSpeaking ? (
        <button
          type="button"
          onClick={speak}
          disabled={!text}
          title={t('voice.play')}
          className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-(--zy-surface-raised) hover:text-(--zy-primary) disabled:opacity-40"
        >
          <Volume2 className="size-4" />
        </button>
      ) : (
        <>
          <button
            type="button"
            onClick={pause}
            title={isPaused ? t('voice.resume') : t('voice.pause')}
            className="flex size-7 items-center justify-center rounded-md text-(--zy-primary) transition-colors hover:bg-(--zy-surface-raised)"
          >
            {isPaused ? <Play className="size-4" /> : <Pause className="size-4" />}
          </button>
          <button
            type="button"
            onClick={stop}
            title={t('voice.stop')}
            className="flex size-7 items-center justify-center rounded-md text-(--zy-destructive) transition-colors hover:bg-(--zy-surface-raised)"
          >
            <Square className="size-4" />
          </button>
        </>
      )}
      {showControls && (
        <div className="ml-1 flex items-center gap-2 border-l border-border pl-2 text-xs text-muted-foreground">
          <Settings2 className="size-3.5" />
          <input
            type="range"
            min="0.5"
            max="2"
            step="0.1"
            value={config.rate}
            onChange={(e) => setConfig((c) => ({ ...c, rate: parseFloat(e.target.value) }))}
            title={`${t('voice.rate')}: ${config.rate.toFixed(1)}`}
            className="h-1 w-12 cursor-pointer appearance-none rounded-full bg-muted accent-(--zy-primary)"
          />
        </div>
      )}
    </div>
  );
}

export default VoiceOutput;
