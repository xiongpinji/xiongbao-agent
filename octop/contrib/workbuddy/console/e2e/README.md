# Console E2E smoke

A small, framework-free Playwright smoke harness for the Workbuddy Console.

It boots a static HTTP server that serves `octop/contrib/workbuddy/console/`
at `/console/*`, drives headless Chromium through the three user-facing pages
(`index.html`, `shell.html`, `ops.html`), and asserts:

- each page loads without an uncaught JavaScript error
- the brand title contains WorkBuddy / Console / Agent
- the chat shell exposes both a composer and a sidebar
- the ops dashboard renders non-empty content
- no subresource request fails (modulo favicons, robots.txt, `/api/health`,
  `/api/channels` and `/api/agents/me/sessions` which are intentionally not
  served by this static harness)

The script imports `playwright` directly via `pathToFileURL`, so no separate
`@playwright/test` install is required — it reuses the project's existing
`vendor/RongXinAI/node_modules/playwright`. If the local Chromium download is
out of sync it auto-falls back to the most recent system-installed build at
`%LOCALAPPDATA%/ms-playwright/chromium-*/chrome-win64/chrome.exe`.

## Run

```bash
node octop/contrib/workbuddy/console/e2e/run-smoke.mjs
```

Exit code `0` = all steps passed; non-zero = at least one assertion failed.
The harness prints a per-step timing summary on success.

## Adding steps

Add another `await step('description', async () => { ... })` call inside
`main()`. Each step gets its own browser context so failures are isolated.
Use the `assert(cond, message)` helper for checks; failing assertions throw
and the step is recorded as failed without aborting the remaining steps.

## Limitations

- Only covers the Console (web) target. RongXinAI's Electron desktop is
  exercised separately by `vendor/RongXinAI` Vitest suites — Spectron was
  not adopted because the package has been unmaintained since 2022.
- The script runs against the on-disk Console HTML/CSS/JS as-is; it does
  not exercise the dashboard API or live LLM round-trips. Use the backend
  integration suite (`make test` in `octop/`) for those.
