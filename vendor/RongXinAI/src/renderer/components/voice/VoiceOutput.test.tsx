// @vitest-environment jsdom

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { VoiceOutput } from './VoiceOutput';

vi.mock('../../services/i18n', () => ({
  i18nService: {
    t: (key: string) => key,
    subscribe: () => () => undefined,
    getLanguage: () => 'zh',
  },
}));

describe('VoiceOutput', () => {
  beforeEach(() => {
    vi.stubGlobal('speechSynthesis', {
      speak: () => {},
      pause: () => {},
      cancel: () => {},
      resume: () => {},
      getVoices: () => [],
      onvoiceschanged: null,
    });
    // jsdom lacks SpeechSynthesisUtterance; provide a no-op class.
    (globalThis as unknown as { SpeechSynthesisUtterance: unknown }).SpeechSynthesisUtterance =
      class {
        lang = '';
        text = '';
        rate = 1;
        pitch = 1;
        volume = 1;
        onstart: unknown = null;
        onend: unknown = null;
        onerror: unknown = null;
        onpause: unknown = null;
        onresume: unknown = null;
      };
  });

  it('renders without crashing', () => {
    expect(() => render(<VoiceOutput text="test" />)).not.toThrow();
  });

  it('renders a play button on first load', () => {
    const { container } = render(<VoiceOutput text="test" />);
    expect(container.querySelector('button')).not.toBeNull();
  });

  it('renders without autoPlay prop', () => {
    expect(() => render(<VoiceOutput text="test" autoPlay />)).not.toThrow();
  });

  it('renders with showControls', () => {
    expect(() => render(<VoiceOutput text="test" showControls />)).not.toThrow();
  });

  it('renders with lang prop', () => {
    expect(() => render(<VoiceOutput text="test" lang="en-US" />)).not.toThrow();
  });

  it('handles empty text', () => {
    expect(() => render(<VoiceOutput text="" />)).not.toThrow();
  });

  it('renders multiple instances independently', () => {
    expect(() => {
      render(<VoiceOutput text="first" />);
      render(<VoiceOutput text="second" />);
    }).not.toThrow();
  });

  it('renders with className', () => {
    expect(() => render(<VoiceOutput text="test" className="my-class" />)).not.toThrow();
  });

  it('does not throw on unmount', () => {
    const { unmount } = render(<VoiceOutput text="test" />);
    expect(() => unmount()).not.toThrow();
  });

  it('renders backend mode when client is supplied', () => {
    const backend = {
      transcribe: async () => ({ text: 'hi' }),
      synthesize: async () => ({ audio: new Blob([new Uint8Array([1, 2])]), mimeType: 'audio/mpeg' }),
    };
    expect(() =>
      render(<VoiceOutput text="hello" backend={backend as any} />),
    ).not.toThrow();
  });

  it('synthesize() is invoked when backend is supplied and user clicks play', async () => {
    const synth = vi.fn(async () => ({
      audio: new Blob([new Uint8Array([1, 2])]),
      mimeType: 'audio/mpeg',
    }));
    const backend = { transcribe: async () => ({ text: 'hi' }), synthesize: synth };

    // jsdom doesn't implement HTMLAudioElement.play(); mock just enough to
    // exercise the backend branch without unhandled promise rejections.
    class FakeAudio {
      src = '';
      playbackRate = 1;
      paused = true;
      currentTime = 0;
      onplay: unknown = null;
      onended: unknown = null;
      onerror: unknown = null;
      onpause: unknown = null;
      async play() {
        return Promise.resolve();
      }
      pause() {
        /* no-op */
      }
    }
    vi.stubGlobal('Audio', FakeAudio as any);
    vi.stubGlobal('URL', {
      ...(URL as any),
      createObjectURL: () => 'blob:fake',
      revokeObjectURL: () => {},
    });

    const { container } = render(<VoiceOutput text="hello" backend={backend as any} />);
    const button = container.querySelector('button') as HTMLButtonElement;
    button.click();
    // synthesize is async; wait for the next microtask cycle.
    await new Promise(r => setTimeout(r, 0));
    expect(synth).toHaveBeenCalledTimes(1);
    expect(synth).toHaveBeenCalledWith(expect.objectContaining({ text: 'hello' }));
  });
});
