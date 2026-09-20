import { expect, test } from 'vitest';
import { workbuddyLight, workbuddyDark } from './workbuddy';
import { classicLight } from './classic-light';
import { resolveThemePlugin, validateTheme } from './plugins';

function contrast(a: string, b: string) {
  const luminance = (hex: string) => {
    const rgb = hex.match(/[a-f\d]{2}/gi)!.map(channel => {
      const v = parseInt(channel, 16) / 255;
      return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    });
    return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
  };
  const values = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

test('Xiongbao provides complete appearances without replacing the default package', () => {
  for (const theme of [workbuddyLight, workbuddyDark]) validateTheme(theme);
  expect(resolveThemePlugin('workbuddy').appearances.light).toBe(workbuddyLight);
  expect(resolveThemePlugin('workbuddy').appearances.dark).toBe(workbuddyDark);
  expect(resolveThemePlugin('unknown').id).toBe('codex');
  expect(workbuddyLight.components['fluid-indicator']).not.toBe(
    classicLight.components['fluid-indicator'],
  );
  expect(classicLight.components['fluid-indicator'].base['border-radius']).toBe('9999px');
});

test('Xiongbao text and primary actions retain AA contrast on their surfaces', () => {
  for (const theme of [workbuddyLight, workbuddyDark]) {
    const t = theme.tokens;
    for (const surface of [t.background, t.surface, t['surface-raised']]) {
      for (const text of [
        t.foreground,
        t['text-muted-foreground'],
        t.primary,
        t.warning,
        t.success,
        t.destructive,
      ]) {
        expect(
          contrast(text, surface),
          `${theme.meta.id}: ${text} on ${surface}`,
        ).toBeGreaterThanOrEqual(4.5);
      }
    }
    expect(
      contrast(t['switch-thumb-foreground'], t['style-work-chat-thumb']),
    ).toBeGreaterThanOrEqual(4.5);
    expect(contrast(t['primary-foreground'], t['primary-strong'])).toBeGreaterThanOrEqual(4.5);
  }
});

test('Xiongbao owns sidebar and legacy warning/error foreground roles', () => {
  for (const theme of [workbuddyLight, workbuddyDark]) {
    const t = theme.tokens;
    expect(t['semantic-sidebar']).toBe(t['surface-raised']);
    expect(t['semantic-sidebar-ring']).toBe(t.primary);
    expect(t['component-palette-amber-500']).toBe(t.warning);
    expect(t['component-palette-yellow-700']).toBe(t.warning);
    expect(t['component-palette-red-500']).toBe(t.destructive);
  }
});

test('Xiongbao ships the brand gold primary and 3px gold left-rail indicator', () => {
  for (const theme of [workbuddyLight, workbuddyDark]) {
    const t = theme.tokens;
    // Gold (dark) / antique-gold (light) is the only saturated accent.
    expect(t.primary === '#FFC107' || t.primary === '#8A6508').toBe(true);
    // Dark-mode text on bright gold; light-mode white text on antique gold.
    // Both pairs clear AA 4.5:1 against the corresponding primary.
    expect(t['primary-foreground'] === '#1A1208' || t['primary-foreground'] === '#FFFFFF').toBe(true);
    expect(contrast(t['primary-foreground'], t.primary)).toBeGreaterThanOrEqual(4.5);
    // Brand red destructive on dark, deep cinnabar on light.
    expect(t.destructive === '#FF7A6B' || t.destructive === '#C53030').toBe(true);
    // Sidebar menu button selected state carries a 3px gold left rail.
    const menu = theme.components['sidebar-menu-button'];
    expect(menu.selected['border-left-width']).toBe('3px');
    expect(menu.selected['border-left-color']).toBe('var(--zy-primary)');
    expect(menu.base['border-radius']).toBe('var(--zy-style-radius-md)');
  }
});
