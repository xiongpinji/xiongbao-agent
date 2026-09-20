import { expect, test } from 'vitest';

import {
  createIMScheduledTaskRequestDetector,
  isReminderSystemTurn,
  looksLikeIMScheduledTaskCandidate,
  normalizeDetectedScheduledTaskRequest,
} from './imScheduledTaskHandler';
import type { IMMessage } from './types';

test('normalizes model-detected IM reminder requests into direct cron.add inputs', () => {
  const scheduleAtInput = '2026-03-15T16:30:00+08:00';
  const runAt = new Date(scheduleAtInput);
  const expectedClock = '16:30';
  const parsed = normalizeDetectedScheduledTaskRequest(
    {
      shouldCreateTask: true,
      scheduleAt: scheduleAtInput,
      reminderBody: '喝饮料',
      taskName: '喝饮料提醒',
    },
    '2分钟后提醒我喝饮料',
    new Date('2026-03-15T16:28:00+08:00'),
  );

  expect(parsed).toBeTruthy();
  expect(parsed!.kind).toBe('create');
  expect(parsed!.reminderBody).toBe('喝饮料');
  expect(parsed!.taskName).toBe('喝饮料提醒');
  expect(parsed!.payloadText).toBe('⏰ 提醒：喝饮料');
  expect(parsed!.delayLabel).toBe('2分钟后');
  expect(parsed!.runAt.toISOString()).toBe(runAt.toISOString());
  expect(new Date(parsed!.scheduleAt).toISOString()).toBe(runAt.toISOString());
  expect(parsed!.confirmationText).toMatch(
    new RegExp(`2分钟后（${expectedClock}）会提醒你喝饮料`, 'u'),
  );
});

test('only uses heuristic as a cheap reminder candidate prefilter', () => {
  expect(looksLikeIMScheduledTaskCandidate('帮我总结一下今天的会议纪要')).toBe(false);
  expect(looksLikeIMScheduledTaskCandidate('2分钟后提醒我喝饮料')).toBe(true);
});

test('rejects detector payloads without a future timezone-aware timestamp', () => {
  expect(
    normalizeDetectedScheduledTaskRequest(
      {
        shouldCreateTask: true,
        scheduleAt: '2026-03-15T16:30:00',
        reminderBody: '喝水',
      },
      '提醒我喝水',
      new Date('2026-03-15T16:28:00+08:00'),
    ),
  ).toBe(null);
});

test('identifies reminder system turns for async IM delivery', () => {
  expect(isReminderSystemTurn([{ type: 'assistant', content: '普通回复' }])).toBe(false);

  expect(
    isReminderSystemTurn([
      { type: 'system', content: '⏰ 提醒：喝饮料' },
      { type: 'assistant', content: '该喝饮料啦！' },
    ]),
  ).toBe(true);
});

test('keeps recognizing legacy reminder system messages during transition', () => {
  expect(
    isReminderSystemTurn([
      { type: 'system', content: 'System: [Sunday, March 15th, 2026 — 4:30 PM] ⏰ 提醒：喝饮料' },
      { type: 'assistant', content: '该喝饮料啦！' },
    ]),
  ).toBe(true);
});

test('recognizes plain reminder text turns during runtime hotfix rollout', () => {
  expect(
    isReminderSystemTurn([
      { type: 'user', content: '⏰ 提醒：该去钉钉打卡啦！别忘了打卡哦～' },
      { type: 'assistant', content: '⏰ 时间到啦，该去打卡了。' },
    ]),
  ).toBe(true);
});

test('detector routes through octop when supplied and parses JSON reply', async () => {
  class FakeWs {
    url: string;
    sentFrames: string[] = [];
    private listeners = new Map<string, Array<(...args: unknown[]) => void>>();
    constructor(url: string) {
      this.url = url;
      // Use a 0ms timeout to push open/message events onto the macrotask queue
      // so they fire AFTER the OctopChatClient registers its `on('message')`
      // handler in response to the resolved `openPromise`.
      setTimeout(() => {
        this.emit('open');
        setTimeout(() => {
          this.emit(
            'message',
            Buffer.from(
              JSON.stringify({
                type: 'chunk',
                delta: JSON.stringify({
                  shouldCreateTask: true,
                  scheduleAt: '2026-04-01T10:00:00+08:00',
                  reminderBody: '喝水',
                  taskName: '喝水提醒',
                }),
              }),
            ),
          );
          setTimeout(() => {
            this.emit('message', Buffer.from(JSON.stringify({ type: 'done' })));
          }, 0);
        }, 0);
      }, 0);
    }
    on(event: string, listener: (...args: unknown[]) => void): void {
      const arr = this.listeners.get(event) ?? [];
      arr.push(listener);
      this.listeners.set(event, arr);
    }
    once(event: string, listener: (...args: unknown[]) => void): void {
      this.on(event, listener);
    }
    emit(event: string, ...args: unknown[]): void {
      for (const l of [...(this.listeners.get(event) ?? [])]) l(...args);
    }
    send(frame: string): void {
      this.sentFrames.push(frame);
    }
    close(): void {
      this.emit('close', 1000);
    }
  }

  const detector = createIMScheduledTaskRequestDetector({
    getLLMConfig: async () => null,
    octop: {
      baseUrl: 'http://octop.local',
      bearer: 'jwt',
      getAgentId: () => 'ag-1',
      imSettings: { skillsEnabled: false },
      WebSocketCtor: FakeWs as unknown as never,
    },
  });

  const msg: IMMessage = {
    id: 'm',
    platform: 'feishu',
    chatId: 'c',
    senderId: 'u',
    content: '5分钟后提醒我喝水',
    timestamp: Date.parse('2026-04-01T09:55:00+08:00'),
  };

  const parsed = await detector(msg);
  expect(parsed).not.toBeNull();
  expect(parsed!.reminderBody).toBe('喝水');
});

test('detector reads getOctopOptions lazily so live settings edits take effect', async () => {
  class ReplayWs {
    url: string;
    sentFrames: string[] = [];
    private listeners = new Map<string, Array<(...args: unknown[]) => void>>();
    constructor(url: string) {
      this.url = url;
      setTimeout(() => {
        this.emit('open');
        setTimeout(() => {
          this.emit(
            'message',
            Buffer.from(
              JSON.stringify({
                type: 'chunk',
                delta: JSON.stringify({
                  shouldCreateTask: true,
                  scheduleAt: '2026-04-01T10:00:00+08:00',
                  reminderBody: '喝水',
                  taskName: '喝水提醒',
                }),
              }),
            ),
          );
          this.emit('message', Buffer.from(JSON.stringify({ type: 'done' })));
          this.emit('close', 1000);
        }, 5);
      }, 0);
    }
    send(payload: string) {
      this.sentFrames.push(payload);
    }
    close(code?: number) {
      this.emit('close', code ?? 1000);
    }
    on(event: string, listener: (...args: unknown[]) => void) {
      const list = this.listeners.get(event) ?? [];
      list.push(listener);
      this.listeners.set(event, list);
    }
    once() {
      this.on.apply(this, arguments as never);
    }
    private emit(event: string, ...args: unknown[]) {
      for (const listener of this.listeners.get(event) ?? []) {
        listener(...args);
      }
    }
  }

  let callsToGetOctopOptions = 0;
  const detector = createIMScheduledTaskRequestDetector({
    getLLMConfig: async () => null,
    getOctopOptions: () => {
      callsToGetOctopOptions += 1;
      return {
        baseUrl: 'http://127.0.0.1:8088',
        bearer: 'jwt',
        getAgentId: async () => 'ag-1',
        imSettings: { skillsEnabled: false },
        WebSocketCtor: ReplayWs as unknown as never,
      };
    },
  });

  const msg: IMMessage = {
    id: 'm-lazy',
    platform: 'feishu',
    chatId: 'c',
    senderId: 'u',
    content: '5分钟后提醒我喝水',
    timestamp: Date.parse('2026-04-01T09:55:00+08:00'),
  };

  const parsed = await detector(msg);
  expect(parsed).not.toBeNull();
  expect(parsed!.reminderBody).toBe('喝水');
  expect(callsToGetOctopOptions).toBeGreaterThanOrEqual(1);
});

test('detector falls back to LLM when getOctopOptions returns null', async () => {
  const detector = createIMScheduledTaskRequestDetector({
    getLLMConfig: async () => ({
      apiKey: 'k',
      baseUrl: 'http://llm.local',
      model: 'm',
    }),
    getOctopOptions: () => null,
  });

  const msg: IMMessage = {
    id: 'm-fallback',
    platform: 'wecom',
    chatId: 'c',
    senderId: 'u',
    content: '不是定时任务',
    timestamp: Date.now(),
  };
  // Non-reminder-like content fails the prefilter and returns null without
  // either LLM or Octop being touched.
  const parsed = await detector(msg);
  expect(parsed).toBeNull();
});
