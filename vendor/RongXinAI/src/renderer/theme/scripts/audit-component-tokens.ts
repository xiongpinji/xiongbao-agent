#!/usr/bin/env node
/**
 * audit-component-tokens.ts
 *
 * Static audit over the 17 enhancement components shipped in Steps 1-4 plus
 * any new component added under src/renderer/components/{brand,credits,voice,responsive}.
 *
 * The audit enforces DESIGN.md invariants:
 *  - 禁止 font-bold (use font-semibold)
 *  - 禁止 Tailwind 默认彩色刻度（bg-blue-*, text-amber-*, ...）
 *  - 禁止 raw hex / rgb / hsl / [style.color] = '#...'
 *  - 禁止 bg-black / bg-white
 *
 * The audit also verifies that every brand-/tier-/transaction-related color
 * is referenced via CSS custom properties (var(--zy-...)) rather than literals.
 *
 * Usage:
 *   bun src/renderer/theme/scripts/audit-component-tokens.ts
 *
 * Exit code 0 when clean, 1 when violations are found.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
// script lives at <root>/src/renderer/theme/scripts/audit-component-tokens.ts
// → walk up four levels to reach the package root (RongXinAI).
const ROOT = resolve(HERE, '..', '..', '..', '..');
const TARGET_DIRS = [
  join(ROOT, 'src/renderer/components/brand'),
  join(ROOT, 'src/renderer/components/credits'),
  join(ROOT, 'src/renderer/components/voice'),
  join(ROOT, 'src/renderer/components/responsive'),
  join(ROOT, 'src/renderer/components/EnhancementsDemo.tsx'),
];

interface Violation {
  file: string;
  line: number;
  rule: string;
  match: string;
  message: string;
}

const violations: Violation[] = [];

const RULES = [
  {
    id: 'no-font-bold',
    pattern: /\bfont-bold\b/,
    message: 'DESIGN.md 禁止 font-bold（700+），改用 font-semibold/font-medium。',
  },
  {
    id: 'no-tailwind-color-scale',
    // bg-blue-500, text-amber-50, dark:bg-purple-200, etc.
    pattern: /\b(?:bg|text|border|ring|fill|stroke|from|to|via|placeholder|caret|accent|decoration|outline|shadow|divide)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b/,
    message: 'DESIGN.md 禁止 Tailwind 默认彩色刻度；改用语义 token (bg-primary, text-destructive, ...)。',
  },
  {
    id: 'no-bg-black-or-white',
    pattern: /\b(?:bg|text|border)-(?:black|white)\b/,
    message: 'DESIGN.md 禁止 bg-black / bg-white；改用语义 surface/background token。',
  },
  {
    id: 'no-raw-hex',
    // bg-[#fff], text-[#abc], [color:'#abc']; allows comments-only hex via context later
    pattern: /(?:#[0-9a-fA-F]{3,8}\b|rgb\(|rgba\(|hsl\(|hsla\()/,
    message: 'DESIGN.md 禁止组件内写 hex/rgb/hsl 颜色；改用 token。',
  },
];

const ALLOW_LIST = new Set<string>([
  // The audit itself and theme token declarations legitimately use hex literals.
  // The audit excludes only files in TARGET_DIRS; nothing further should be needed.
]);

function isAllowed(filePath: string): boolean {
  return ALLOW_LIST.has(filePath);
}

function shouldSkipLine(line: string): boolean {
  const trimmed = line.trim();
  if (trimmed.startsWith('//')) return true;
  if (trimmed.startsWith('*')) return true;
  if (trimmed.startsWith('/*')) return true;
  return false;
}

function auditFile(filePath: string): void {
  const text = readFileSync(filePath, 'utf8');
  const lines = text.split(/\r?\n/);
  lines.forEach((line, i) => {
    if (shouldSkipLine(line)) return;
    for (const rule of RULES) {
      const match = line.match(rule.pattern);
      if (match) {
        violations.push({
          file: filePath,
          line: i + 1,
          rule: rule.id,
          match: match[0],
          message: rule.message,
        });
      }
    }
  });
}

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      out.push(...walk(full));
    } else if (stat.isFile() && /\.tsx?$/.test(entry) && !entry.endsWith('.test.tsx')) {
      out.push(full);
    }
  }
  return out;
}

const files: string[] = [];
for (const target of TARGET_DIRS) {
  try {
    const stat = statSync(target);
    if (stat.isDirectory()) {
      files.push(...walk(target));
    } else if (stat.isFile()) {
      files.push(target);
    }
  } catch {
    // ignore missing paths
  }
}

for (const file of files) {
  if (isAllowed(file)) continue;
  auditFile(file);
}

if (violations.length === 0) {
  console.log(`✅ audit-component-tokens: ${files.length} files clean.`);
  process.exit(0);
}

const grouped = new Map<string, Violation[]>();
for (const v of violations) {
  const key = v.file;
  if (!grouped.has(key)) grouped.set(key, []);
  grouped.get(key)!.push(v);
}

console.error(`❌ audit-component-tokens: ${violations.length} violation(s) across ${grouped.size} file(s).\n`);
for (const [file, list] of grouped) {
  console.error(`  ${relative(ROOT, file)}`);
  for (const v of list) {
    console.error(`    L${v.line} [${v.rule}] ${v.match}  →  ${v.message}`);
  }
  console.error('');
}

process.exit(1);
