const fs = require('fs');

const voiceInputButton = `// @vitest-environment jsdom

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { VoiceInputButton } from './VoiceInputButton';

vi.mock('../../services/i18n', () => ({
  i18nService: {
    t: (key: string) => {
      const voiceMap = { 'voice.start': '点击开始', 'voice.listening': '聆听中', 'voice.stop': '停止' };
      return voiceMap[key] ?? key;
    },
    subscribe: () => () => undefined,
    getLanguage: () => 'zh',
  },
}));

class MockSpeechRecognition {
  continuous = false;
  interimResults = false;
  lang = '';
  maxAlternatives = 1;
  onresult = null;
  onerror = null;
  onend = null;
  onstart = null;
  started = false;
  stopped = false;

  start() {
    this.started = true;
    this.onstart?.();
  }
  stop() {
    this.stopped = true;
    setTimeout(() => this.onend?.(), 0);
  }
  abort() {
    this.stopped = true;
    setTimeout(() => this.onend?.(), 0);
  }
}

const mockRecognition = new MockSpeechRecognition();

vi.stubGlobal('SpeechRecognition', class {
  constructor() { return mockRecognition; }
});
vi.stubGlobal('webkitSpeechRecognition', class {
  constructor() { return mockRecognition; }
});

describe('VoiceInputButton', () => {
  it('renders a button', () => {
    render(<VoiceInputButton />);
    const btn = screen.getByRole('button');
    expect(btn).toBeDefined();
    expect(btn).toHaveProperty('title', expect.stringMatching(/点击开始|start/i));
  });

  it('starts recognition on click', () => {
    render(<VoiceInputButton />);
    fireEvent.click(screen.getByRole('button'));
    expect(mockRecognition.started).toBe(true);
  });

  it('stops recognition on second click', () => {
    render(<VoiceInputButton />);
    fireEvent.click(screen.getByRole('button'));
    expect(mockRecognition.started).toBe(true);
    fireEvent.click(screen.getByRole('button'));
    expect(mockRecognition.stopped).toBe(true);
  });

  it('sets interim transcript on result', () => {
    const onTranscript = vi.fn();
    render(<VoiceInputButton onTranscript={onTranscript} />);
    fireEvent.click(screen.getByRole('button'));
    act(() => {
      mockRecognition.onresult?.({ results: [[{ transcript: 'hello world', isFinal: true }]] });
    });
    expect(onTranscript).toHaveBeenCalledWith('hello world');
  });

  it('disables button when disabled prop is true', () => {
    render(<VoiceInputButton disabled />);
    const btn = screen.getByRole('button') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it('shows listening state when started', () => {
    render(<VoiceInputButton />);
    fireEvent.click(screen.getByRole('button'));
    const btn = screen.getByRole('button');
    expect(btn).toHaveProperty('title', expect.stringMatching(/聆听中|listening/i));
  });

  it('calls onError when recognition errors', () => {
    const onError = vi.fn();
    render(<VoiceInputButton onError={onError} />);
    fireEvent.click(screen.getByRole('button'));
    act(() => {
      mockRecognition.onerror?.({ error: 'no-speech' });
    });
    expect(onError).toHaveBeenCalled();
  });
});
`;

const voiceOutput = `// @vitest-environment jsdom

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { VoiceOutput } from './VoiceOutput';

vi.mock('../../services/i18n', () => ({
  i18nService: {
    t: (key: string) => {
      const voiceMap = {
        'voice.play': '播放',
        'voice.pause': '暂停',
        'voice.resume': '继续',
        'voice.stop': '停止',
        'voice.rate': '语速',
      };
      return voiceMap[key] ?? key;
    },
    subscribe: () => () => undefined,
    getLanguage: () => 'zh',
  },
}));

let mockSpeak = vi.fn();
let mockPause = vi.fn();
let mockCancel = vi.fn();
let mockResume = vi.fn();

vi.stubGlobal('speechSynthesis', {
  speak: mockSpeak,
  pause: mockPause,
  cancel: mockCancel,
  resume: mockResume,
  getVoices: () => [
    { name: 'Microsoft Huihui', lang: 'zh-CN' },
    { name: 'Google US English', lang: 'en-US' },
  ],
  onvoiceschanged: null,
});

describe('VoiceOutput', () => {
  beforeEach(() => {
    mockSpeak = vi.fn();
    mockPause = vi.fn();
    mockCancel = vi.fn();
    mockResume = vi.fn();
    vi.stubGlobal('speechSynthesis', {
      speak: mockSpeak,
      pause: mockPause,
      cancel: mockCancel,
      resume: mockResume,
      getVoices: () => [{ name: 'zh', lang: 'zh-CN' }],
      onvoiceschanged: null,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders text content', () => {
    render(<VoiceOutput text="test" />);
    expect(screen.getByText('test')).toBeDefined();
  });

  it('calls speak on mount by default', () => {
    render(<VoiceOutput text="test" />);
    expect(mockSpeak).toHaveBeenCalled();
  });

  it('does not auto-play when autoPlay is false', () => {
    render(<VoiceOutput text="test" autoPlay={false} />);
    expect(mockSpeak).not.toHaveBeenCalled();
  });

  it('renders pause button after speaking starts', async () => {
    render(<VoiceOutput text="test" />);
    await new Promise((r) => setTimeout(r, 10));
    const pauseBtn = screen.getByTitle(/暂停|pause/i);
    expect(pauseBtn).toBeDefined();
  });

  it('calls pause on pause button click', async () => {
    render(<VoiceOutput text="test" />);
    fireEvent.click(screen.getByRole('button'));
    await new Promise((r) => setTimeout(r, 10));
    fireEvent.click(screen.getByTitle(/暂停|pause/i));
    expect(mockPause).toHaveBeenCalled();
  });

  it('calls cancel on stop button click', async () => {
    render(<VoiceOutput text="test" />);
    fireEvent.click(screen.getByRole('button'));
    await new Promise((r) => setTimeout(r, 10));
    fireEvent.click(screen.getByTitle(/停止|stop/i));
    expect(mockCancel).toHaveBeenCalled();
  });

  it('auto-plays when autoPlay is true', () => {
    render(<VoiceOutput text="auto" autoPlay />);
    expect(mockSpeak).toHaveBeenCalled();
  });

  it('renders rate slider when showControls', () => {
    render(<VoiceOutput text="test" showControls />);
    const slider = screen.getByRole('slider');
    expect(slider).toBeDefined();
  });

  it('does not crash when voices are empty', () => {
    vi.stubGlobal('speechSynthesis', {
      speak: mockSpeak,
      pause: mockPause,
      cancel: mockCancel,
      resume: mockResume,
      getVoices: () => [],
      onvoiceschanged: null,
    });
    expect(() => render(<VoiceOutput text="test" />)).not.toThrow();
  });

  it('cleans up speech on unmount', () => {
    const { unmount } = render(<VoiceOutput text="test" />);
    unmount();
    expect(mockCancel).toHaveBeenCalled();
  });

  it('respects lang prop', () => {
    render(<VoiceOutput text="test" lang="en-US" />);
    expect(mockSpeak).toHaveBeenCalled();
    const utterance = mockSpeak.mock.calls[0][0];
    expect(utterance.lang).toBe('en-US');
  });
});
`;

const responsive = `// @vitest-environment jsdom

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { renderHook, act } from '@testing-library/react';
import { Show, Hide, useIsMobile } from './Responsive';

describe('Show', () => {
  it('renders children when condition is true', () => {
    render(<Show when={true}>content</Show>);
    expect(screen.getByText('content')).toBeDefined();
  });

  it('does not render when condition is false', () => {
    render(<Show when={false}>content</Show>);
    expect(screen.queryByText('content')).toBeNull();
  });

  it('renders fallback when provided and condition is false', () => {
    render(<Show when={false} fallback={<span>fallback</span>}>content</Show>);
    expect(screen.getByText('fallback')).toBeDefined();
  });
});

describe('Hide', () => {
  it('does not render children when condition is true', () => {
    render(<Hide when={true}>content</Hide>);
    expect(screen.queryByText('content')).toBeNull();
  });

  it('renders children when condition is false', () => {
    render(<Hide when={false}>content</Hide>);
    expect(screen.getByText('content')).toBeDefined();
  });
});

describe('MobileSheet', () => {
  it('renders children in a sheet when mobile', () => {
    const { container } = render(
      <MobileSheet title="Sheet Title" open onClose={() => {}}>
        <p>Sheet Content</p>
      </MobileSheet>,
    );
    expect(screen.getByText('Sheet Title')).toBeDefined();
    expect(screen.getByText('Sheet Content')).toBeDefined();
  });

  it('renders null on desktop', () => {
    global.innerWidth = 1280;
    const { container } = render(
      <MobileSheet title="Sheet" open onClose={() => {}}>
        <p>Content</p>
      </MobileSheet>,
    );
    expect(screen.queryByText('Sheet')).toBeNull();
  });
});

describe('ScrollToTop', () => {
  it('renders a button that scrolls to top on click', () => {
    global.scrollTo = vi.fn();
    render(<ScrollToTop />);
    const btn = screen.getByRole('button');
    fireEvent.click(btn);
    expect(global.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
  });

  it('hides when scrolled less than threshold', () => {
    global.scrollY = 0;
    global.pageYOffset = 0;
    render(<ScrollToTop />);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('shows when scrolled past threshold', () => {
    global.scrollY = 1000;
    global.pageYOffset = 1000;
    render(<ScrollToTop />);
    expect(screen.getByRole('button')).toBeDefined();
  });
});

describe('useIsMobile', () => {
  it('returns true when width < 768', () => {
    global.innerWidth = 375;
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(true);
  });

  it('returns false when width >= 768', () => {
    global.innerWidth = 1024;
    const { result } = renderHook(() => useIsMobile());
    expect(result.current).toBe(false);
  });
});
`;

fs.writeFileSync('src/renderer/components/voice/VoiceInputButton.test.tsx', voiceInputButton, 'utf8');
console.log('Written VoiceInputButton.test.tsx');
fs.writeFileSync('src/renderer/components/voice/VoiceOutput.test.tsx', voiceOutput, 'utf8');
console.log('Written VoiceOutput.test.tsx');
fs.writeFileSync('src/renderer/components/responsive/Responsive.test.tsx', responsive, 'utf8');
console.log('Written Responsive.test.tsx');
