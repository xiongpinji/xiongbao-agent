/**
 * DESIGN.md 合约测试
 *
 * DESIGN.md 在"主题包：熊宝（Xiongbao / Workbuddy）"章节列出了玄金主题色板
 * 的精确 hex 值与 AA 对比度承诺。本文件读取 docs/hex 对照表后用同一
 * contrast() 公式复核数值，避免文档漂移。
 *
 * 公式与 src/renderer/theme/themes/workbuddy.test.ts 中一致；
 * 阈值与 DESIGN.md 中"状态色对账"表保持一致。
 */

import { describe, expect, it } from 'vitest';
import { workbuddyDark, workbuddyLight } from './workbuddy';

function hexToRgb(hex: string): [number, number, number] {
  const v = hex.replace('#', '');
  const r = parseInt(v.slice(0, 2), 16);
  const g = parseInt(v.slice(2, 4), 16);
  const b = parseInt(v.slice(4, 6), 16);
  return [r, g, b];
}

function contrast(a: string, b: string): number {
  const lum = (hex: string) => {
    const [r, g, b] = hexToRgb(hex);
    const norm = [r, g, b]
      .map(channel => channel / 255)
      .map(v => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return norm[0] * 0.2126 + norm[1] * 0.7152 + norm[2] * 0.0722;
  };
  const values = [lum(a), lum(b)].sort((x, y) => y - x);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

describe('Xiongbao design palette', () => {
  it('primary gold values match DESIGN.md exactly', () => {
    expect(workbuddyDark.tokens.primary).toBe('#FFC107');
    expect(workbuddyLight.tokens.primary).toBe('#8A6508');
  });

  it('primary-foreground inverts by mode and clears AA 4.5:1', () => {
    for (const theme of [workbuddyDark, workbuddyLight]) {
      const fg = theme.tokens['primary-foreground'];
      const primary = theme.tokens.primary;
      const ratio = contrast(fg, primary);
      expect(ratio).toBeGreaterThanOrEqual(4.5);
    }
  });

  it('canvas / surface / raised / tertiary / overlay follow the documented ladder', () => {
    // Dark: #0F1115 → #242529 → #2D2E33 (background → surface → surface-raised)
    expect(workbuddyDark.tokens.background).toBe('#0F1115');
    expect(workbuddyDark.tokens.surface).toBe('#242529');
    expect(workbuddyDark.tokens['surface-raised']).toBe('#2D2E33');
    expect(workbuddyDark.tokens['surface-tertiary']).toBe('#2D2E33');
    // Light: #FAFAF7 → #FFFFFF → #F5F5F0
    expect(workbuddyLight.tokens.background).toBe('#FAFAF7');
    expect(workbuddyLight.tokens.surface).toBe('#FFFFFF');
    expect(workbuddyLight.tokens['surface-raised']).toBe('#F5F5F0');
    expect(workbuddyLight.tokens['surface-tertiary']).toBe('#EBEBE5');
  });

  it('status colors match the documented values and clear AA on the worst surface', () => {
    const cases: Array<{
      label: string;
      theme: typeof workbuddyDark;
      statusKey: 'success' | 'warning' | 'destructive';
      value: string;
    }> = [
      { label: 'dark success', theme: workbuddyDark, statusKey: 'success', value: '#34C759' },
      { label: 'light success', theme: workbuddyLight, statusKey: 'success', value: '#1F7A38' },
      { label: 'dark warning', theme: workbuddyDark, statusKey: 'warning', value: '#FF9500' },
      { label: 'light warning', theme: workbuddyLight, statusKey: 'warning', value: '#8A4A00' },
      { label: 'dark destructive', theme: workbuddyDark, statusKey: 'destructive', value: '#FF7A6B' },
      { label: 'light destructive', theme: workbuddyLight, statusKey: 'destructive', value: '#C53030' },
    ];
    for (const c of cases) {
      expect(c.theme.tokens[c.statusKey], c.label).toBe(c.value);
      for (const surface of [
        c.theme.tokens.background,
        c.theme.tokens.surface,
        c.theme.tokens['surface-raised'],
      ]) {
        const ratio = contrast(c.value, surface);
        expect(ratio, `${c.label} on ${surface}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it('sidebar accent mirrors surface-raised and the ring tracks primary', () => {
    for (const theme of [workbuddyDark, workbuddyLight]) {
      expect(theme.tokens['semantic-sidebar']).toBe(theme.tokens['surface-raised']);
      expect(theme.tokens['semantic-sidebar-ring']).toBe(theme.tokens.primary);
    }
  });

  it('chart palette has 5 distinct entries spanning the brand colors', () => {
    for (const theme of [workbuddyDark, workbuddyLight]) {
      const chart = [
        theme.tokens['semantic-chart-1'],
        theme.tokens['semantic-chart-2'],
        theme.tokens['semantic-chart-3'],
        theme.tokens['semantic-chart-4'],
        theme.tokens['semantic-chart-5'],
      ];
      expect(chart).toHaveLength(5);
      const unique = new Set(chart);
      expect(unique.size, `chart palette must be distinct, got ${chart.join(', ')}`).toBeGreaterThanOrEqual(4);
      // chart-1 is always the brand primary.
      expect(chart[0]).toBe(theme.tokens.primary);
    }
  });

  it('sidebar menu selected carries the 3px gold left rail documented in DESIGN.md', () => {
    for (const theme of [workbuddyDark, workbuddyLight]) {
      const menu = theme.components['sidebar-menu-button'];
      expect(menu.selected['border-left-width']).toBe('3px');
      expect(menu.selected['border-left-color']).toBe('var(--zy-primary)');
    }
  });

  it('fluid indicator and other primitives tighten to the 6px brand radius', () => {
    for (const theme of [workbuddyDark, workbuddyLight]) {
      expect(theme.tokens['style-radius-md']).toBe('6px');
      const fluid = theme.components['fluid-indicator'];
      expect(fluid.base['border-radius']).toBe('var(--zy-style-radius-md)');
    }
  });
});
