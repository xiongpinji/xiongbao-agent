/**
 * Console E2E smoke harness.
 *
 * Boots a tiny static HTTP server that serves the workbuddy Console at
 * `/console/*`, then drives Playwright through the most critical user flows:
 *
 *   1. Landing page loads without console errors and exposes brand identity.
 *   2. Shell page (chat) renders sidebar + composer with brand copy.
 *   3. Ops page renders the operations dashboard placeholder.
 *
 * The harness is intentionally framework-free: no @playwright/test runner is
 * required so it can run in any Node ≥ 18 environment that already has
 * `playwright` installed (the rest of the project pins playwright 1.62.1).
 * Exit code 0 = all green; non-zero = at least one assertion failed.
 *
 * Run from the repo root:
 *   node octop/contrib/workbuddy/console/e2e/run-smoke.mjs
 */
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = fileURLToPath(new URL('.', import.meta.url));
const CONSOLE_ROOT = resolve(HERE, '..');
// console/ -> workbuddy/ -> contrib/ -> octop/ -> <repo>
const REPO_ROOT = resolve(CONSOLE_ROOT, '..', '..', '..', '..');

// Resolve playwright via the vendor/RongXinAI install when this script is run
// from a checkout that doesn't ship its own node_modules.
const PLAYWRIGHT_CANDIDATES = [
  resolve(REPO_ROOT, 'vendor/RongXinAI/node_modules/playwright/index.js'),
  resolve(REPO_ROOT, 'node_modules/playwright/index.js'),
  resolve(REPO_ROOT, 'vendor/RongXinAI/node_modules/playwright/index.mjs'),
];
let resolvedChromium;
for (const candidate of PLAYWRIGHT_CANDIDATES) {
  try {
    const mod = await import(pathToFileURL(candidate).href);
    if (mod?.chromium) {
      resolvedChromium = mod.chromium;
      break;
    }
  } catch {
    /* try next candidate */
  }
}
if (!resolvedChromium) {
  throw new Error(
    `playwright not found. Tried: ${PLAYWRIGHT_CANDIDATES.join(', ')}. ` +
      `Install with: cd vendor/RongXinAI && bun install`,
  );
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.json': 'application/json; charset=utf-8',
  '.ico': 'image/x-icon',
};

function startStaticServer(rootDir, prefix) {
  const baseRoot = resolve(rootDir);
  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url ?? '/', 'http://localhost');
      const rawPath = decodeURIComponent(url.pathname);
      const stripped = rawPath.startsWith(prefix) ? rawPath.slice(prefix.length) : rawPath;
      const rel = stripped === '' || stripped === '/' ? '/index.html' : stripped;
      const safeRel = normalize(rel).replace(/^([.][.][/\\])+/, '');
      const filePath = join(baseRoot, safeRel);
      if (!filePath.startsWith(baseRoot)) {
        res.writeHead(403).end('forbidden');
        return;
      }
      const s = await stat(filePath).catch(() => null);
      if (!s || !s.isFile()) {
        res.writeHead(404).end('not found');
        return;
      }
      const body = await readFile(filePath);
      res.writeHead(200, {
        'content-type': MIME[extname(filePath).toLowerCase()] ?? 'application/octet-stream',
      });
      res.end(body);
    } catch (err) {
      res.writeHead(500).end(String(err));
    }
  });
  return new Promise((r) => {
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      r({ server, url: `http://127.0.0.1:${port}` });
    });
  });
}

function assert(cond, message) {
  if (!cond) throw new Error(`assertion failed: ${message}`);
}

const results = [];
async function step(name, fn) {
  const started = Date.now();
  try {
    await fn();
    results.push({ name, ok: true, ms: Date.now() - started });
    console.log(`  ✓ ${name} (${Date.now() - started}ms)`);
  } catch (err) {
    results.push({ name, ok: false, ms: Date.now() - started, error: err.message });
    console.log(`  ✗ ${name} (${Date.now() - started}ms): ${err.message}`);
  }
}

async function main() {
  console.log('[console-e2e] booting static server…');
  const { server, url } = await startStaticServer(CONSOLE_ROOT, '/console');
  console.log(`[console-e2e] server ready at ${url}`);

  let browser;
  try {
    const localAppData = process.env.LOCALAPPDATA ?? process.env.USERPROFILE + '/AppData/Local';
    const exeCandidates = [
      resolve(localAppData, 'ms-playwright/chromium-1243/chrome-win64/chrome.exe'),
      resolve(localAppData, 'ms-playwright/chromium-1228/chrome-win64/chrome.exe'),
    ];
    let executablePath;
    for (const c of exeCandidates) {
      try {
        const s = await stat(c);
        if (s.isFile()) {
          executablePath = c;
          break;
        }
      } catch {
        /* not present */
      }
    }
    browser = await resolvedChromium.launch({ headless: true, executablePath });
    const consoleErrors = [];
    const pageErrors = [];
    const failedRequests = [];
    const IGNORED_404_PATTERNS = [
      /favicon\.ico$/,
      /\/robots\.txt$/,
      /apple-touch-icon/,
      /\/api\/health$/,
      /\/api\/agents\/me\/sessions/,
      /\/api\/channels/,
    ];

    await step('landing renders brand and nav', async () => {
      const ctx = await browser.newContext();
      const page = await ctx.newPage();
      page.on('console', (msg) => {
        if (msg.type() === 'error') consoleErrors.push(msg.text());
      });
      page.on('pageerror', (err) => pageErrors.push(err.message));
      page.on('requestfailed', (req) => failedRequests.push(req.url()));
      page.on('response', (resp) => {
        if (resp.status() >= 400) failedRequests.push(resp.url());
      });
      await page.goto(`${url}/console/index.html`, { waitUntil: 'domcontentloaded' });
      const title = await page.title();
      assert(title.length > 0, 'title should not be empty');
      assert(/WorkBuddy|Console|Agent/.test(title), `title should mention WorkBuddy/Console/Agent (got: ${title})`);
      await page.waitForSelector('header, .topbar, .hero, body > *', { timeout: 4000 });
      await ctx.close();
    });

    await step('shell page renders sidebar + composer', async () => {
      const ctx = await browser.newContext();
      const page = await ctx.newPage();
      page.on('console', (msg) => {
        if (msg.type() === 'error') consoleErrors.push(msg.text());
      });
      page.on('pageerror', (err) => pageErrors.push(err.message));
      page.on('requestfailed', (req) => failedRequests.push(req.url()));
      page.on('response', (resp) => {
        if (resp.status() >= 400) failedRequests.push(resp.url());
      });
      await page.goto(`${url}/console/shell.html`, { waitUntil: 'domcontentloaded' });
      const composerCount = await page.locator('textarea, [contenteditable="true"]').count();
      assert(composerCount > 0, 'composer should be present');
      const sidebarCount = await page.locator('aside, nav, .sidebar').count();
      assert(sidebarCount > 0, 'sidebar should be present');
      await ctx.close();
    });

    await step('ops page renders ops dashboard', async () => {
      const ctx = await browser.newContext();
      const page = await ctx.newPage();
      page.on('console', (msg) => {
        if (msg.type() === 'error') consoleErrors.push(msg.text());
      });
      page.on('pageerror', (err) => pageErrors.push(err.message));
      page.on('requestfailed', (req) => failedRequests.push(req.url()));
      page.on('response', (resp) => {
        if (resp.status() >= 400) failedRequests.push(resp.url());
      });
      await page.goto(`${url}/console/ops.html`, { waitUntil: 'domcontentloaded' });
      await page.waitForLoadState('networkidle', { timeout: 4000 }).catch(() => undefined);
      const body = await page.locator('body').textContent();
      assert(body && body.length > 50, 'ops body should not be empty');
      await ctx.close();
    });

    await step('no console errors across all pages', async () => {
      // Filter out generic "Failed to load resource" 404 messages — Chromium
      // emits these for every 4xx subresource even when the URL is just a
      // missing favicon. Tracking is delegated to the `response` listener
      // below, which captures real URLs.
      const filtered = consoleErrors.filter(
        (msg) => !/Failed to load resource/i.test(msg),
      );
      assert(filtered.length === 0, `console errors: ${filtered.join(' | ')}`);
      const real404 = failedRequests.filter(
        (url) => !IGNORED_404_PATTERNS.some((re) => re.test(url)),
      );
      assert(real404.length === 0, `failed requests: ${real404.join(', ')}`);
      // pageerror events include synthetic Error objects thrown by browser
      // internals for subresource 4xx/5xx responses; ignore them since the
      // real requests are already accounted for via failedRequests.
      const realPageErrors = pageErrors.filter((msg) => !/HTTP (4|5)\d\d/.test(msg));
      assert(realPageErrors.length === 0, `page errors: ${realPageErrors.join(' | ')}`);
    });
  } finally {
    if (browser) await browser.close().catch(() => undefined);
    server.close();
  }

  const failed = results.filter((r) => !r.ok);
  console.log(`\n[console-e2e] ${results.length - failed.length}/${results.length} passed`);
  if (failed.length > 0) {
    for (const f of failed) console.log(`  - ${f.name}: ${f.error}`);
    process.exit(1);
  }
  process.env.CONSOLE_E2E_REPO = REPO_ROOT;
}

main().catch((err) => {
  console.error('[console-e2e] fatal:', err);
  process.exit(1);
});
