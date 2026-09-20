import { BackgroundFit, BackgroundKind, BackgroundTexture } from '../background/background';
import { classicDark } from './classic-dark';
import { classicLight } from './classic-light';
import type { ThemeDefinition } from './types';

/**
 * Workbuddy — Xiongbao (熊宝) brand theme.
 *
 * Lacquered black canvas with antique-gold primary (#FFC107).
 * Dark mode is the hero: deep neutrals (#0F1115 → #3A3B40) with gold
 * as the only saturated accent. Light mode is a parchment / soft-ivory
 * counterpart that keeps the same gold-on-paper feel so the brand reads
 * consistently across appearances.
 *
 * Interaction, layout and selector coverage all stay in the shared classic
 * package; this file only swaps tokens and a handful of control shapes
 * (gold left-rail indicator on the sidebar, slightly tighter radii).
 */
function createWorkbuddy(dark: boolean): ThemeDefinition {
  const base = dark ? classicDark : classicLight;

  // Canvas — deep lacquer (dark) / ivory paper (light)
  const canvas = dark ? '#0F1115' : '#FAFAF7';
  const sidebar = dark ? '#1A1B1F' : '#F2F1EC';
  const surface = dark ? '#242529' : '#FFFFFF';
  const surfaceRaised = dark ? '#2D2E33' : '#F5F5F0';
  const surfaceTertiary = dark ? '#2D2E33' : '#EBEBE5';
  const ink = dark ? '#F8FAFC' : '#1A1A1A';
  // Brightened slightly so #9DA0A5 on the deepest surface (#2D2E33) still
  // clears 4.5:1 — the contract test walks every text × surface combo.
  const muted = dark ? '#9DA0A5' : '#666666';
  const border = dark ? 'rgba(255,255,255,0.10)' : '#E0DFD9';
  const borderSubtle = dark ? 'rgba(255,255,255,0.06)' : '#EBEAE4';

  // Brand: gold primary, antique-gold secondary, cinnabar brand red.
  // Dark uses the saturated brand values; light uses darker, AA-compliant
  // counterparts so every status color clears 4.5:1 on parchment.
  // Light-mode gold tuned for AA contrast with white text on parchment.
  const gold = dark ? '#FFC107' : '#8A6508';
  const goldHover = dark ? '#E6B800' : '#70500A';
  const goldSoft = dark ? 'rgba(255,193,7,0.14)' : 'rgba(138,101,8,0.16)';
  const antiqueGold = dark ? '#D4A85A' : '#6E5224';
  const brandRed = dark ? '#FF4444' : '#C53030';
  const brandBlue = dark ? '#4B7BF5' : '#2E5BD9';

  const success = dark ? '#34C759' : '#1F7A38';
  // Slightly darker light-mode warning to clear 4.5:1 on the parchment surface.
  const warning = dark ? '#FF9500' : '#8A4A00';
  const danger = dark ? '#FF7A6B' : brandRed;

  const components = structuredClone(base.components);

  // Heading: keep serif brand voice but a touch tighter (lacquer-shop signage).
  components.heading.base['font-weight'] = '600';
  components.heading.base['letter-spacing'] = '0.01em';

  // Sidebar menu: a 3px gold left rail when active — the workbuddy signature.
  components['sidebar-menu-button'].base['border-radius'] = 'var(--zy-style-radius-md)';
  components['sidebar-menu-button'].selected['border-left-color'] = 'var(--zy-primary)';
  components['sidebar-menu-button'].selected['border-left-width'] = '3px';
  components['sidebar-menu-button'].selected['padding-left'] = 'calc(0.5rem - 3px)';
  components['sidebar-menu-button'].selected['background-color'] = 'var(--zy-primary-muted)';
  components['sidebar-menu-button'].selected.color = 'var(--zy-primary)';

  // Tighter, more "lacquered" corners.
  components['input-submit'].base['border-radius'] = 'var(--zy-style-radius-md)';
  components['fluid-indicator'].base['border-radius'] = 'var(--zy-style-radius-md)';
  components['fluid-hover-indicator'].base['border-radius'] = 'var(--zy-style-radius-md)';
  components['fluid-indicator'].base['background-color'] = 'var(--zy-surface)';
  components['fluid-indicator'].base['box-shadow'] = 'var(--zy-style-shadow-subtle)';
  components['fluid-tab'].selected.color = 'var(--zy-primary)';
  components['fluid-tab'].base.opacity = '1';
  components['page-tabs-trigger'].selected.color = 'var(--zy-primary)';
  components['page-tabs-indicator'].base['background-color'] = 'var(--zy-primary)';

  // Card lifts on hover — the spec's "translateY(-1px)" reads as a soft glow.
  components.card.hover.translate = '0 -1px';
  components.card.hover['box-shadow'] = 'var(--zy-style-shadow-card)';

  // Switch thumb follows the primary foreground so the gold button reads AA.
  components['switch-thumb'].checked['background-color'] = 'var(--zy-primary-foreground)';

  return {
    meta: {
      id: dark ? 'workbuddy-dark' : 'workbuddy-light',
      name: dark ? '熊宝 · 玄金' : '熊宝 · 绢白',
      description: dark
        ? 'Lacquered black canvas with gold primary — Xiongbao dark mode'
        : 'Parchment / soft ivory with gold primary — Xiongbao light mode',
      appearance: dark ? 'dark' : 'light',
    },
    components,
    branding: {
      logo: '/src/renderer/assets/brand/xiongbao/logo-icon.png',
      mascot: '/src/renderer/assets/brand/xiongbao/mascot.png',
      productName: '熊宝 Agent',
    },
    background: {
      // Flat lacquered canvas — no texture, just the brand palette.
      // Dark: deep charcoal sidebar color #1A1B1F painted behind everything.
      // Light: warm ivory #F2F1EC, matching the parchment feel of the gold.
      kind: BackgroundKind.Color,
      color: dark ? '#1A1B1F' : '#F2F1EC',
      opacity: 1,
      texture: BackgroundTexture.Paper,
      fit: BackgroundFit.Cover,
    },
    tokens: {
      ...base.tokens,
      success,
      warning,
      destructive: danger,
      'style-destructive-confirm': brandRed,

      // Sidebar inherits the lacquered sidebar surface and the gold ring.
      // Test expects semantic-sidebar to mirror surface-raised (the classic baseline).
      'semantic-sidebar': surfaceRaised,
      'semantic-sidebar-foreground': ink,
      'semantic-sidebar-primary': gold,
      // Dark text on bright gold for both modes — tests enforce 4.5:1 across modes.
      'semantic-sidebar-primary-foreground': '#1A1208',
      'semantic-sidebar-accent': surfaceRaised,
      'semantic-sidebar-accent-foreground': ink,
      'semantic-sidebar-border': border,
      'semantic-sidebar-ring': gold,

      // Chart palette: gold, brand red, antique gold, jade, blue.
      'semantic-chart-1': gold,
      'semantic-chart-2': antiqueGold,
      'semantic-chart-3': brandRed,
      'semantic-chart-4': success,
      'semantic-chart-5': brandBlue,

      // Brand tokens — gold primary, brand red destructive.
      primary: gold,
      'primary-strong': gold,
      'primary-hover': goldHover,
      // Dark text on bright dark-mode gold; white text on deeper light-mode gold.
      // Both clear AA 4.5:1 against the corresponding primary.
      'primary-foreground': dark ? '#1A1208' : '#FFFFFF',
      'primary-muted': goldSoft,
      ring: gold,

      // Canvas / surface stack.
      background: canvas,
      foreground: ink,
      surface,
      'surface-foreground': ink,
      'surface-raised': surfaceRaised,
      'surface-tertiary': surfaceTertiary,
      'surface-overlay': surface,

      accent: surfaceRaised,
      'accent-foreground': ink,

      'chat-user': surfaceRaised,
      'chat-user-foreground': ink,
      'chat-bot': canvas,
      'chat-bot-foreground': ink,

      'text-primary': ink,
      'text-muted': muted,
      'text-muted-foreground': muted,

      border,
      'border-subtle': borderSubtle,
      'input-border': border,

      'scroll-thumb': dark ? '#3A3B40' : '#C7C5BD',
      'scroll-thumb-hover': muted,

      'gradient-1': canvas,
      'gradient-2': surface,

      'skill-blue-background': goldSoft,
      'skill-blue-foreground': antiqueGold,

      'model-tag-neutral-background': surfaceRaised,
      'model-tag-neutral-foreground': muted,
      'model-tag-neutral-border': border,
      'model-tag-violet-background': dark ? '#3A2E33' : '#F2E2D9',
      'model-tag-violet-foreground': dark ? '#F29A97' : '#A03836',
      'model-tag-violet-border': border,
      'model-tag-green-background': dark ? '#1F3D2A' : '#E4EAD8',
      'model-tag-green-foreground': dark ? '#7CD992' : '#3D7B45',
      'model-tag-green-border': border,

      // Credit tier badges — gold-themed variants so the brand voice carries through.
      // Pro uses a subtle gold wash; Enterprise stays brand-red warm to set it apart from Pro.
      'tier-free-background': surfaceRaised,
      'tier-free-foreground': muted,
      'tier-basic-background': dark ? '#1F2A3A' : '#E2E8F0',
      'tier-basic-foreground': dark ? '#7AA0E8' : '#2E5BD9',
      'tier-pro-background': goldSoft,
      'tier-pro-foreground': gold,
      'tier-enterprise-background': dark ? '#3D1F1F' : '#F4E1DE',
      'tier-enterprise-foreground': brandRed,

      // Credit transaction types — Xiongbao brand-aware: spend=red, earn/refund=green,
      // recharge=gold (the brand primary), gift=brand-red warm (re-using the Enterprise hue).
      'transaction-earn-background': dark ? '#1F3D2A' : '#E4EAD8',
      'transaction-earn-foreground': success,
      'transaction-spend-background': dark ? '#3D1F1F' : '#F4E1DE',
      'transaction-spend-foreground': brandRed,
      'transaction-recharge-background': goldSoft,
      'transaction-recharge-foreground': gold,
      'transaction-gift-background': dark ? '#3D1F1F' : '#F4E1DE',
      'transaction-gift-foreground': brandRed,
      'transaction-refund-background': dark ? '#1F3D2A' : '#E4EAD8',
      'transaction-refund-foreground': success,

      // Bottom-sheet / modal scrim — slightly stronger on dark lacquered canvas.
      'overlay-scrim': dark ? 'rgba(0, 0, 0, 0.7)' : 'rgba(0, 0, 0, 0.5)',

      // Voice: brand-red cinnabar so the recording dot reads on lacquered canvas
      // and stays consistent with destructive semantics (no second red introduced).
      'voice-recording': brandRed,
      'voice-recording-foreground': dark ? '#1A1208' : '#FFFFFF',

      // Headings lean serif for the brand voice, body stays system sans.
      'style-font-heading': '"Songti SC", "STSong", "Noto Serif CJK SC", serif',

      // Tighter radius family — 6px is the brand baseline.
      radius: '0.375rem',
      'style-radius-sm': '4px',
      'style-radius-md': '6px',
      'style-radius-lg': '8px',
      'style-radius-xl': '10px',
      'style-radius-2xl': '0.75rem',
      'style-radius-3xl': '1rem',

      'style-work-chat-track': sidebar,
      'style-work-chat-thumb': surface,
      'style-work-chat-thumb-radius': '6px',
      'style-switch-thumb': '#FFFFFF',
      // The chat thumb in dark mode is the dark surface (#242529), so the
      // switch foreground reads light. In light mode the chat thumb is white,
      // so the foreground is dark. The test enforces 4.5:1 contrast here.
      'switch-thumb-foreground': ink,

      // Shadows: a faint gold glow when the primary is the focus element.
      'style-shadow-glow-accent': dark
        ? '0 0 0 2px rgba(255,193,7,0.25)'
        : '0 0 0 2px rgba(230,184,0,0.22)',
      'style-shadow-card': dark
        ? '0 1px 3px rgb(0 0 0 / 0.45), 0 1px 2px rgb(0 0 0 / 0.30)'
        : '0 1px 3px rgb(0 0 0 / 0.06), 0 1px 2px rgb(0 0 0 / 0.04)',
      'style-shadow-popover': dark
        ? '0 10px 28px rgb(0 0 0 / 0.55), 0 1px 4px rgb(0 0 0 / 0.35)'
        : '0 8px 24px rgb(0 0 0 / 0.10), 0 1px 4px rgb(0 0 0 / 0.04)',
      'style-shadow-modal': dark
        ? '0 12px 32px rgb(0 0 0 / 0.55), 0 1px 4px rgb(0 0 0 / 0.30)'
        : '0 4px 16px rgb(0 0 0 / 0.08), 0 1px 3px rgb(0 0 0 / 0.04)',
      'style-shadow-elevated': dark
        ? '0 4px 14px rgb(0 0 0 / 0.50), 0 1px 3px rgb(0 0 0 / 0.30)'
        : '0 4px 12px rgb(0 0 0 / 0.10), 0 1px 3px rgb(0 0 0 / 0.04)',

      // Editor surface: a slightly raised lacquer panel.
      'component-editor-background': dark ? '#1A1B1F' : '#FFFCF6',
      'component-editor-foreground': ink,
      'component-editor-gutter': muted,
      'component-editor-selection': dark ? 'rgba(255,193,7,0.22)' : 'rgba(255,193,7,0.30)',
      'component-editor-active-line': dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)',
      'component-editor-deleted': dark ? 'rgba(255,68,68,0.18)' : 'rgba(212,43,43,0.12)',
      'component-editor-inserted': dark ? 'rgba(52,199,89,0.15)' : 'rgba(30,160,60,0.12)',
      'component-editor-indent': dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
      'component-editor-indent-active': dark ? 'rgba(255,255,255,0.22)' : 'rgba(0,0,0,0.22)',
      'component-editor-deleted-chunk': dark ? 'rgba(255,68,68,0.15)' : 'rgba(255,80,80,0.15)',
      'component-editor-inserted-chunk': dark ? 'rgba(60,180,100,0.15)' : 'rgba(60,180,100,0.15)',
      'component-editor-changed': 'rgba(255,200,0,0.25)',
      'component-editor-search': dark ? 'rgba(255,193,7,0.30)' : 'rgba(255,193,7,0.30)',
      'component-editor-search-selected': dark ? 'rgba(255,193,7,0.50)' : 'rgba(230,184,0,0.50)',
      'component-editor-error': brandRed,
      'component-editor-indent-fallback': dark ? 'rgba(128,128,128,0.15)' : 'rgba(128,128,128,0.15)',
      'component-editor-indent-active-fallback': dark ? 'rgba(128,128,128,0.35)' : 'rgba(128,128,128,0.35)',

      // Palette overrides — amber family tracks the warning role so legacy
      // amber usage (badges, icons) stays on-brand.
      'component-palette-amber-50': dark ? '#3A2F12' : '#FBF4DC',
      'component-palette-amber-200': dark ? '#7A5E1E' : '#E8D29E',
      'component-palette-amber-400': warning,
      'component-palette-amber-500': warning,
      'component-palette-amber-700': warning,
      'component-palette-amber-800': warning,
      'component-palette-amber-950': '#3A2F12',

      // Yellow family — the warning role. We bind yellow-500..800 to the
      // warning token so legacy yellow usage still tracks the brand.
      'component-palette-yellow-50': dark ? '#3A2F12' : '#FBF4DC',
      'component-palette-yellow-200': dark ? '#7A5E1E' : '#F2DC9F',
      'component-palette-yellow-400': warning,
      'component-palette-yellow-500': warning,
      'component-palette-yellow-600': warning,
      'component-palette-yellow-700': warning,
      'component-palette-yellow-800': warning,
      'component-palette-yellow-900': dark ? '#5C4416' : '#7A5E1E',

      // Reds — brand red on dark, deep cinnabar on light for AA contrast.
      'component-palette-red-50': dark ? '#3D1F1F' : '#F4E1DE',
      'component-palette-red-200': dark ? '#7A4040' : '#DDBDB7',
      'component-palette-red-400': danger,
      'component-palette-red-500': danger,
      'component-palette-red-600': danger,
      'component-palette-red-700': danger,
      'component-palette-red-800': danger,
      'component-palette-red-900': '#5C1F1F',

      'component-palette-blue-400': brandBlue,
      'component-palette-blue-500': brandBlue,
      'component-palette-blue-600': brandBlue,

      'component-palette-green-400': success,
      'component-palette-green-500': success,
      'component-palette-green-600': success,

      'component-palette-orange-500': warning,
      'component-palette-orange-600': warning,

      'component-palette-gray-300': border,
      'component-palette-gray-400': muted,
      'component-palette-gray-600': muted,
    },
  };
}

export const workbuddyLight = createWorkbuddy(false);
export const workbuddyDark = createWorkbuddy(true);
