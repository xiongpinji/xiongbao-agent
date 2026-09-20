declare module 'node-pty' {
  export interface IPty {
    pid: number;
    cols: number;
    rows: number;
    process: string;
    onData: import('node:events').EventEmitter;
    onExit: import('node:events').EventEmitter;
    on(
      event: 'data',
      listener: (data: string) => void,
    ): this;
    on(
      event: 'exit',
      listener: (exitCode: number, signal?: number) => void,
    ): this;
    resize(cols: number, rows: number): void;
    write(data: string): void;
    kill(signal?: string): void;
    pause(): void;
    resume(): void;
  }

  export interface IPtyForkOptions {
    name?: string;
    cols?: number;
    rows?: number;
    cwd?: string;
    env?: Record<string, string>;
    uid?: number;
    gid?: number;
    encoding?: string | null;
    handleFlowControl?: boolean;
    useConpty?: boolean;
    allowWindowsInheritance?: boolean;
  }

  export function spawn(
    file: string,
    args?: string[] | string,
    options?: IPtyForkOptions,
  ): IPty;
}
