import { randomUUID } from 'crypto';
import { EventEmitter } from 'events';
import { spawn as childProcessSpawn } from 'child_process';

const DEFAULT_COLUMNS = 100;
const DEFAULT_DEFAULT_ROWS = 30;

// Lazy-loaded so tests and callers that never start a real terminal don't pay
// for `node-pty` — which on Windows requires electron-rebuild and may be
// unavailable in environments that ship without a usable native binary. When
// the native module is missing, we fall back to `child_process.spawn` and
// adapt the small subset of `pty.IPty` events we actually use.
type PtyLike = {
  on(event: 'data', listener: (data: string) => void): unknown;
  on(event: 'exit', listener: (code: number, signal?: number) => void): unknown;
  write(data: string): void;
  resize(columns: number, rows: number): void;
  kill(): void;
};

type PtySpawner = (file: string, args: string[], options: {
  name?: string;
  cols?: number;
  rows?: number;
  cwd?: string;
  env?: Record<string, string>;
}) => PtyLike;

let cachedSpawner: PtySpawner | null = null;
let nodePtyLoadFailed = false;

function loadNodePty(): PtySpawner | null {
  if (cachedSpawner) return cachedSpawner;
  if (nodePtyLoadFailed) return null;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const pty = require('node-pty') as {
      spawn: (file: string, args: string[], options: {
        name?: string;
        cols?: number;
        rows?: number;
        cwd?: string;
        env?: Record<string, string>;
      }) => PtyLike;
    };
    cachedSpawner = ((file, args, options) => pty.spawn(file, args, {
      name: options.name ?? 'xterm-256color',
      cols: options.cols ?? DEFAULT_COLUMNS,
      rows: options.rows ?? DEFAULT_DEFAULT_ROWS,
      cwd: options.cwd,
      env: options.env,
    })) as PtySpawner;
    return cachedSpawner;
  } catch (err) {
    nodePtyLoadFailed = true;
    console.warn('[AuthTerminalService] node-pty unavailable, falling back to child_process:', err);
    return null;
  }
}

function fallbackSpawner(): PtySpawner {
  return (file, args, options) => {
    const child = childProcessSpawn(file, args, {
      cwd: options.cwd,
      env: options.env,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    const proxy: PtyLike = {
      on(event: 'data' | 'exit', listener: unknown) {
        if (event === 'data') {
          const dataListener = listener as (data: string) => void;
          child.stdout?.on('data', (chunk: Buffer) => dataListener(chunk.toString('utf8')));
          child.stderr?.on('data', (chunk: Buffer) => dataListener(chunk.toString('utf8')));
        } else {
          const exitListener = listener as (code: number, signal?: number) => void;
          child.on('exit', (code, signal) => {
            const numericCode = typeof code === 'number' ? code : 0;
            exitListener(numericCode, signal as unknown as number | undefined);
          });
        }
        return proxy;
      },
      write(data) {
        child.stdin?.write(data);
      },
      resize() {
        // No real PTY resize when running in fallback mode; no-op.
      },
      kill() {
        child.kill();
      },
    };
    return proxy;
  };
}

export interface AuthTerminalStartedEvent {
  id: string;
  profileId: string;
  methodId: string;
}

export interface AuthTerminalExitedEvent extends AuthTerminalStartedEvent {
  exitCode: number;
  signal?: number;
}

type ActiveTerminal = AuthTerminalStartedEvent & { terminal: PtyLike };

/** Runs ACP terminal authentication separately from the ACP JSON-RPC stdio connection. */
export class AuthTerminalService extends EventEmitter {
  private readonly terminals = new Map<string, ActiveTerminal>();

  constructor(spawnPty?: PtySpawner) {
    super();
    this.spawnPty = spawnPty ?? loadNodePty() ?? fallbackSpawner();
  }

  private readonly spawnPty: PtySpawner;

  start(input: {
    profileId: string;
    methodId: string;
    executable: string;
    baseArgs: string[];
    authArgs: string[];
    cwd: string;
    environment: Record<string, string | undefined>;
    authEnvironment?: Record<string, string>;
  }): AuthTerminalStartedEvent {
    const id = randomUUID();
    const started = { id, profileId: input.profileId, methodId: input.methodId };
    const environment = Object.fromEntries(
      Object.entries({ ...input.environment, ...input.authEnvironment }).filter(
        (entry): entry is [string, string] => typeof entry[1] === 'string',
      ),
    );
    const terminal = this.spawnPty(input.executable, [...input.baseArgs, ...input.authArgs], {
      name: 'xterm-256color',
      cols: DEFAULT_COLUMNS,
      rows: DEFAULT_DEFAULT_ROWS,
      cwd: input.cwd,
      env: environment,
    });
    const active: ActiveTerminal = { ...started, terminal };
    this.terminals.set(id, active);
    terminal.on('data', data => this.emit('data', { id, data }));
    terminal.on('exit', (exitCode: number, signal?: number) => {
      if (!this.terminals.delete(id)) return;
      this.emit('exit', { ...started, exitCode, signal } satisfies AuthTerminalExitedEvent);
    });
    return started;
  }

  write(id: string, data: string): void {
    const terminal = this.require(id);
    terminal.terminal.write(data);
  }

  resize(id: string, columns: number, rows: number): void {
    const terminal = this.require(id);
    terminal.terminal.resize(Math.max(1, columns), Math.max(1, rows));
  }

  cancel(id: string): void {
    this.require(id).terminal.kill();
  }

  dispose(): void {
    for (const terminal of this.terminals.values()) terminal.terminal.kill();
    this.terminals.clear();
  }

  private require(id: string): ActiveTerminal {
    const terminal = this.terminals.get(id);
    if (!terminal) throw new Error('The authentication terminal is no longer active.');
    return terminal;
  }
}
