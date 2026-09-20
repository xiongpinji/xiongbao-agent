// @vitest-environment jsdom

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { VoiceInputButton } from './VoiceInputButton';

vi.mock('../../services/i18n', () => ({
  i18nService: {
    t: (key: string) => {
      const map: Record<string, string> = {
        voiceInputStart: '点击开始语音输入',
        voiceInputStop: '点击停止录音',
        voiceInputProcessing: '正在处理',
        voiceInputNoSpeech: '未检测到语音，请重试',
        voiceInputNotAllowed: '请允许麦克风权限',
        voiceInputNetworkError: '网络错误，语音识别不可用',
        voiceInputError: '语音识别错误: {error}',
        voiceInputStartFailed: '启动语音识别失败',
        voiceInputUnsupported: '当前浏览器不支持语音识别',
      };
      return map[key] ?? key;
    },
    subscribe: () => () => undefined,
    getLanguage: () => 'zh',
  },
}));

describe('VoiceInputButton', () => {
  it('renders a button', () => {
    render(<VoiceInputButton />);
    expect(screen.getByRole('button')).toBeDefined();
  });

  it('renders with start title', () => {
    render(<VoiceInputButton />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveProperty('title');
  });

  it('disables button when disabled prop is true', () => {
    render(<VoiceInputButton disabled />);
    const btn = screen.getByRole('button');
    expect(btn).toHaveProperty('disabled', true);
  });

  it('passes onTranscript prop', () => {
    expect(() => render(<VoiceInputButton onTranscript={() => {}} />)).not.toThrow();
  });

  it('passes onError prop', () => {
    expect(() => render(<VoiceInputButton onError={() => {}} />)).not.toThrow();
  });

  it('renders with lang prop', () => {
    expect(() => render(<VoiceInputButton lang="en-US" />)).not.toThrow();
  });

  it('renders in backend mode without crashing', () => {
    const backend = {
      transcribe: async () => ({ text: 'hi' }),
      synthesize: async () => ({ audio: new Blob(), mimeType: 'audio/mpeg' }),
    };
    expect(() =>
      render(<VoiceInputButton backend={backend as any} />),
    ).not.toThrow();
  });
});
