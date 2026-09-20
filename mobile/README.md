# Mobile / PWA Shell (熊宝 Agent)

A standalone progressive web app that talks directly to the Octop backend via
HTTPS + WebSocket. Lives **outside** the Electron build pipeline, ships as a
static asset that can be hosted on any CDN / served by Octop itself at `/mobile`.

## Goals

1. Reuse Octop `/api/agents/{id}/chat/ws` and `/api/auth/login` over the
   network — no Electron IPC bridge.
2. Mobile-first layout (≤ 480px viewport), works on iOS Safari and Android
   Chrome, installable to home screen as a PWA.
3. Avoid ripping out the desktop bundle. The Electron build is still the
   primary desktop surface.
4. Reuse shadcn/ui primitives from `src/shared/components/ui` and ai-elements
   from `src/shared/components/ai-elements` where they don't depend on
   `window.electron.*`.

## Non-goals

- Re-implementing the full desktop experience. PWA is a chat-first surface.
- Native Push notifications on iOS (Safari does not support Web Push on iOS).
- Offline-first mode (no Service Worker cache for chat history).

## Layout

```
mobile/
├── index.html              # PWA entry, viewport meta, manifest link
├── manifest.webmanifest    # PWA manifest
├── service-worker.js       # offline shell + icon cache (no chat history)
├── icons/                  # 192/512 PWA icons
├── src/
│   ├── main.tsx            # React entry
│   ├── App.tsx             # mobile shell
│   ├── api/
│   │   ├── client.ts       # Octop REST client
│   │   └── chatSocket.ts   # /api/agents/{id}/chat/ws wrapper
│   ├── components/
│   │   ├── AgentList.tsx
│   │   ├── ChatScreen.tsx
│   │   └── LoginScreen.tsx
│   └── styles.css          # mobile tokens
├── vite.config.ts          # separate Vite build (no Electron plugin)
└── README.md
```

## Build

```bash
cd mobile
bun install            # or: npm install
bun run typecheck      # tsc --noEmit
bun run build          # vite build → mobile/dist/
```

The `dist/` directory is fully static — copy it into Octop's static mount, or
host it behind Nginx / any CDN.

> **Note:** `mobile/` is its own workspace. React / Vite / TypeScript must be
> installed via `bun install` before `bun run typecheck` or `bun run build`
> will work. Unit tests use Node's built-in `--experimental-transform-types`
> flag, so they don't need a separate build step.

## Auth

The PWA uses Octop's `/api/auth/login` endpoint and stores the resulting
access token in `localStorage`. The token is refreshed transparently by the
client when 401 is returned. There is **no** refresh-token rotation on mobile —
when the access token expires, the user is sent back to the login screen.

> Trust boundary: anyone with `localStorage` access can read the token. This is
> acceptable for the PWA because the same threat exists on a desktop browser;
> the user is expected to lock the device.

## Chat

`src/api/chatSocket.ts` opens a WebSocket to
`${baseUrl}/api/agents/{agent_id}/chat/ws?token={token}` and follows the same
frame protocol used by the Electron desktop dashboard:

- inbound `{type: "user_turn", text}` and `{type: "ping"}`
- outbound stream frames, `chunk`, `error`, `done`

## PWA Install

When the page is served over HTTPS (or `localhost`), the browser shows an
"Add to Home Screen" prompt. The `manifest.webmanifest` declares:

- `name` / `short_name`: 熊宝 Agent
- `start_url`: `/mobile/`
- `display`: `standalone`
- `theme_color` / `background_color`: brand colors from DESIGN.md

## What's missing (intentional)

- Voice input — desktop has it via `OctopVoiceClient`; mobile reuses the same
  HTTP endpoint once the iOS Safari WebKit SpeechRecognition bug is fixed.
- Skill marketplace — desktop-only; will be added once the marketplace backend
  ships (P3-3).
- IM channel binding — desktop-only.

## Tests

There is no Vite test setup for the mobile shell yet. The chat socket has its
own unit test under `mobile/src/api/chatSocket.test.ts` that uses a `FakeWS`.
