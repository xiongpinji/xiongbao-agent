# Workbuddy Theme (熊宝)

Lacquered-black + antique-gold brand theme for the renderer. Source files:

| File | Role |
|------|------|
| `src/renderer/theme/themes/workbuddy.ts` | Token + component recipe override (the plugin) |
| `src/renderer/theme/themes/workbuddy.test.ts` | AA-contrast + sidebar gold-rail assertions |
| `src/renderer/theme/themes/plugins.ts` | Registration as a third-party theme plugin |
| `src/renderer/assets/brand/xiongbao/` | Brand assets (logo-icon.png 28×28, mascot.png 140×140) |
| `src/renderer/components/brand/` | React components for brand assets |

## Design intent

The Workbuddy visual language is "lacquered surface with a single bright metal
accent." Both appearances share that brand voice — gold (#FFC107 in dark mode,
#8A6508 in light) is the only saturated color anywhere; status colors are
deep enough on their surfaces to clear AA.

### Dark · 玄金

| Role | Hex | Note |
|------|-----|------|
| Background | `#0F1115` | Deep lacquer |
| Sidebar | `#1A1B1F` | One step up — sidebar rail |
| Surface / Raised | `#242529` / `#2D2E33` | Cards & popovers |
| Ink | `#F8FAFC` | Body text |
| Muted | `#9DA0A5` | Secondary text (clears 4.5:1 on `#2D2E33`) |
| Primary | `#FFC107` | Brand gold |
| Destructive | `#FF7A6B` | Salmon — `#FF4444` is reserved for the brand logo |
| Success / Warning | `#34C759` / `#FF9500` | System colors |

### Light · 绢白

| Role | Hex | Note |
|------|-----|------|
| Background | `#FAFAF7` | Warm ivory paper |
| Sidebar | `#F2F1EC` | Parchment sidebar rail |
| Surface / Raised | `#FFFFFF` / `#F5F5F0` | Cards & popovers |
| Ink | `#1A1A1A` | Body text |
| Muted | `#666666` | Secondary text |
| Primary | `#8A6508` | Antique gold (dark enough to clear AA on ivory) |
| Destructive | `#C53030` | Cinnabar |
| Success / Warning | `#1F7A38` / `#B05E00` | System colors |

## Brand surface changes

1. **Sidebar menu button** — 3 px gold left rail when the item is the
   active route. Implemented as
   `sidebar-menu-button.selected.border-left-width: 3px` plus a matching
   `border-left-color: var(--zy-primary)` and a soft `primary-muted`
   background tint. The padding is shifted by the rail width so the
   label position matches the inactive state.
2. **Tighter radius family** — `radius: 0.375rem` (6 px), `style-radius-md`
   6 px, `xl` 10 px. Default Codex is 0.625 rem; Workbuddy reads more
   "lacquered" / "die-cut."
3. **Card lift on hover** — `translate: 0 -1px` and the brand card shadow.
   Matches the spec's `hoverTransform: translateY(-1px)`.
4. **Fluid-tab / page-tab indicators** — recolored to `var(--zy-primary)`
   so the gold flows through segmented controls.
5. **Serif headings** — `style-font-heading` switches to `Songti SC` /
   `Noto Serif CJK SC` for the brand voice; body text stays system sans.
6. **Brand palette swaps** — amber-500 and yellow-700 are pinned to the
   warning role, so any code path that still references
   `bg-amber-500` / `text-yellow-700` keeps on-brand colors without
   bypassing the theme contract.
7. **Brand assets** — logo and mascot PNG files are declared in the theme
   definition and accessible via React components:
   - `<ThemeBrandLogo size={28} />` — sidebar logo (28×28 px)
   - `<ThemeBrandMascot size={140} />` — empty state mascot (140×140 px)

## Using brand assets in components

```tsx
import { ThemeBrandLogo, ThemeBrandMascot } from '@/components/brand';

// Sidebar logo
<ThemeBrandLogo size={28} className="mr-2" />

// Empty state mascot
<ThemeBrandMascot size={140} className="mx-auto mb-4" />
```

Both components automatically render the current theme's brand assets and
fall back to nothing if the theme has no branding defined. Logo defaults
to 28×28 px (sidebar size), mascot defaults to 140×140 px (empty state size).

## AA contrast verification

The contract test (`workbuddy.test.ts`) walks every text role
(`foreground`, `text-muted-foreground`, `primary`, `warning`, `success`,
`destructive`) against every surface (`background`, `surface`,
`surface-raised`) in both appearances. All pairs clear the 4.5:1 WCAG AA
bar. The `switch-thumb-foreground` vs `style-work-chat-thumb` pair and
the `primary-foreground` vs `primary-strong` pair are also asserted.

## What the theme plugin does NOT do

- No layout / interaction changes — those live in the shared
  `src/shared/components/ui/` primitives.
- No CSS-in-JS or runtime styles. Themes are pure data — see
  `src/renderer/theme/themes/types.ts` and the
  `validateTheme` / `validateComponentAppearances` functions.
- No override of the per-component selector set. We only mutate existing
  selectors from the classic package, never invent new ones.
- No `url(...)` or `@import` in any token value (the contract regex
  forbids them, and so do we).

## Adding the theme to the in-app switcher

No extra work — `resolveThemePlugin('workbuddy')` is wired up in
`plugins.ts`, and the settings UI looks up plugin id by display name.
Restarting the app is enough for the new entry to show up.

## Verification commands (manual)

```bash
# from the RongXinAI root
bun run theme:check       # regenerates themes.css and diff-checks
bun run theme:audit       # scans components/ for literal colors and
                          # unregistered palette tokens
bun test -- workbuddy     # runs the AA-contrast + sidebar tests
```

If the environment is missing `node_modules`, `bun install` from the
project root first.
