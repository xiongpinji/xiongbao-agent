/**
 * Tests for the Windows NSIS packaging prerequisites audit.
 *
 * P1-4 deliverable: a guard that fires whenever an icon asset, BMP, or
 * installer wiring silently disappears from the repository. The script
 * (``scripts/verify-windows-packaging.cjs``) is the source of truth; this
 * suite exercises its core checks against a fixture directory so it can
 * run without depending on the real ``build/`` tree.
 */

import { describe, expect, it } from 'vitest';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

function writeFixture(filePath: string, bytes: Buffer): void {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, bytes);
}

function makeBmp(width = 32, height = 32): Buffer {
  const rowSize = Math.ceil((width * 3) / 4) * 4;
  const pixelDataSize = rowSize * height;
  const headerSize = 54;
  const buf = Buffer.alloc(headerSize + pixelDataSize);
  buf.write('BM', 0, 'ascii');
  buf.writeUInt32LE(buf.length, 2);
  buf.writeUInt32LE(headerSize, 10);
  buf.writeUInt32LE(40, 14);
  buf.writeInt32LE(width, 18);
  buf.writeInt32LE(height, 22);
  buf.writeUInt16LE(1, 26);
  buf.writeUInt16LE(24, 28);
  return buf;
}

function makeIco(imageCount = 6): Buffer {
  // 6-byte directory entry * count + 16-byte ICONDIR header
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0); // reserved
  header.writeUInt16LE(1, 2); // type = icon
  header.writeUInt16LE(imageCount, 4);
  // Append 16 bytes of ICONDIRENTRY-equivalent padding so we satisfy the
  // 22-byte minimum header length checked by the audit script.
  return Buffer.concat([header, Buffer.alloc(16)]);
}

function makeIcns(): Buffer {
  const buf = Buffer.alloc(8);
  buf.write('icns', 0, 'ascii');
  buf.writeUInt32BE(8, 4);
  return buf;
}

interface FixtureOptions {
         withBmp?: boolean;
         withIco?: boolean;
         withIcns?: boolean;
         withPng?: boolean;
         withInstaller?: boolean;
       }

       const INSTALLER_STUB = [
         '// Test stub for verify-windows-packaging fixtures.',
         '// Forces the script to recognise a PowerShell + VBS + NSIS handoff.',
         'export function installWindowsNsis() {',
         '  // shell out to powershell.exe with a .ps1 launcher; uses wscript.exe',
         '  // .vbs helper; signals "NSIS finish" via Start-Process event log.',
         '  void powershell.exe;',
         '  void wscript.exe;',
         '  void ".ps1";',
         '  void ".vbs";',
         '  void "NSIS finish";',
         '}',
         '',
       ].join('\n');

       function seed(root: string, opts: FixtureOptions = {}): void {
         const all = {
           withBmp: true,
           withIco: true,
           withIcns: true,
           withPng: true,
           withInstaller: true,
           ...opts,
         };
  if (all.withPng) {
    for (const size of [16, 24, 32, 48, 64, 128, 256, 512, 1024]) {
      writeFixture(path.join(root, `build/icons/png/${size}x${size}.png`), Buffer.from([0]));
    }
  }
  if (all.withIco) {
    writeFixture(path.join(root, 'build/icons/win/icon.ico'), makeIco());
  }
  if (all.withIcns) {
    writeFixture(path.join(root, 'build/icons/mac/icon.icns'), makeIcns());
  }
         if (all.withBmp) {
           writeFixture(
             path.join(root, 'build/installer-assets/installerHeader.bmp'),
             makeBmp(),
           );
           writeFixture(
             path.join(root, 'build/installer-assets/installerSidebar.bmp'),
             makeBmp(164, 314),
           );
           writeFixture(
             path.join(root, 'build/installer-assets/uninstallerSidebar.bmp'),
             makeBmp(164, 314),
           );
         }
         if (all.withInstaller) {
           writeFixture(
             path.join(root, 'src/main/libs/appUpdateInstaller.ts'),
             Buffer.from(INSTALLER_STUB, 'utf8'),
           );
         }
       }

function runAudit(cwd: string): { code: number; output: string } {
  /*
   * Resolve the script against the vitest cwd (vendor/RongXinAI), not the
   * test file's location, because vitest's `__dirname` is the compiled test
   * output in some configurations.
   */
  const script = path.resolve(
    process.cwd(),
    'scripts/verify-windows-packaging.cjs',
  );
  try {
    const output = execFileSync('node', [script], {
      cwd,
      stdio: 'pipe',
      encoding: 'utf8',
      env: { ...process.env, ZHIYUAN_PACKAGE_ROOT: cwd },
    });
    return { code: 0, output };
  } catch (err) {
    const e = err as { status: number | null; stdout: Buffer; stderr: Buffer };
    return {
      code: e.status ?? 1,
      output: `${e.stdout.toString('utf8')}${e.stderr.toString('utf8')}`,
    };
  }
}

describe('verify-windows-packaging.cjs', () => {
  it('passes when every asset is present and well-formed', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'win-pack-'));
    seed(root);
    const result = runAudit(root);
    expect(result.code).toBe(0);
    expect(result.output).toContain('PASS');
    fs.rmSync(root, { recursive: true, force: true });
  });

  it('fails when the Windows ICO container is malformed', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'win-pack-'));
    seed(root);
    // Overwrite with garbage that fails the type check.
    writeFixture(path.join(root, 'build/icons/win/icon.ico'), Buffer.alloc(22));
    const result = runAudit(root);
    expect(result.code).toBe(1);
    expect(result.output).toMatch(/Windows \.ico/);
    fs.rmSync(root, { recursive: true, force: true });
  });

  it('fails when NSIS sidebar BMP is not 24-bit', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'win-pack-'));
    seed(root);
    // Forge a 32-bit BMP by tampering with the bits-per-pixel field.
    const buf = makeBmp();
    buf.writeUInt16LE(32, 28);
    writeFixture(path.join(root, 'build/installer-assets/installerSidebar.bmp'), buf);
    const result = runAudit(root);
    expect(result.code).toBe(1);
    expect(result.output).toMatch(/Sidebar BMP/);
    fs.rmSync(root, { recursive: true, force: true });
  });

  it('fails when an icon PNG size is missing', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'win-pack-'));
    seed(root, { withPng: false });
    const result = runAudit(root);
    expect(result.code).toBe(1);
    expect(result.output).toMatch(/PNG 16x16/);
    fs.rmSync(root, { recursive: true, force: true });
  });

  it('fails when macOS ICNS magic is wrong', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'win-pack-'));
    seed(root);
    writeFixture(path.join(root, 'build/icons/mac/icon.icns'), Buffer.alloc(8));
    const result = runAudit(root);
    expect(result.code).toBe(1);
    expect(result.output).toMatch(/macOS \.icns/);
    fs.rmSync(root, { recursive: true, force: true });
  });
});
