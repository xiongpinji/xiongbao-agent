import { expect, test } from 'vitest';

import { AuthTerminalService } from './authTerminalService';

test('keeps terminal authentication output outside the ACP stdio transport', async () => {
  // Stub PtySpawner-compatible fake: mimics a tiny subset of node-pty's IPty
  // surface (data/exit events + write/resize/kill). Kept here so the test
  // runs without depending on node-pty or child_process IPC.
  const service = new AuthTerminalService(
    (_file, _args, _options) => {
      const listeners: { data?: (data: string) => void; exit?: (code: number, signal?: number) => void } = {};
      return {
        on(event: 'data' | 'exit', listener: unknown) {
          if (event === 'data') listeners.data = listener as (data: string) => void;
          else listeners.exit = listener as (code: number, signal?: number) => void;
          queueMicrotask(() => {
            listeners.data?.('signed in');
            listeners.exit?.(0, 0);
          });
          return undefined;
        },
        write: () => undefined,
        resize: () => undefined,
        kill: () => undefined,
      };
    },
  );
  const output: string[] = [];
  const completion = new Promise<{ exitCode: number }>(resolve => {
    service.on('exit', event => resolve(event));
  });
  service.on('data', event => output.push(event.data));

  service.start({
    profileId: 'agent',
    methodId: 'terminal-login',
    executable: '/agent',
    baseArgs: ['login'],
    authArgs: [],
    cwd: process.cwd(),
    environment: process.env as Record<string, string>,
  });

  await expect(completion).resolves.toMatchObject({ exitCode: 0 });
  expect(output.join('')).toContain('signed in');
});
