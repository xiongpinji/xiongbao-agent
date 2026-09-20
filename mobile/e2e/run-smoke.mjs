/**
 * Static-server + Playwright smoke test for the mobile PWA shell.
 *
 * Boots a tiny static HTTP server rooted at `mobile/`, then drives Chromium:
 *   1. Login screen renders brand + form.
 *   2. Submitting the form with an unreachable baseUrl surfaces an error.
 *   3. The PWA manifest and service-worker.js are reachable.
 *
 * Run:
 *   node mobile/e2e/run-smoke.mjs
 */

import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const MOBILE_ROOT = path.join(REPO_ROOT, 'mobile');
const PORT = 5177;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.mjs': 'application/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
};

function startServer() {
  const server = http.createServer((req, res) => {
    const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
    let target = path.join(MOBILE_ROOT, urlPath);
    if (target.endsWith(path.sep) || target.endsWith('/')) target = path.join(target, 'index.html');
    if (!target.startsWith(MOBILE_ROOT)) {
      res.statusCode = 403;
      return res.end('forbidden');
    }
    fs.stat(target, (err, stat) => {
      if (err || !stat.isFile()) {
        res.statusCode = 404;
        return res.end('not found');
      }
      res.setHeader('Content-Type', MIME[path.extname(target)] ?? 'application/octet-stream');
      res.setHeader('Cache-Control', 'no-store');
      fs.createReadStream(target).pipe(res);
    });
  });
  return new Promise((resolve) => server.listen(PORT, '127.0.0.1', () => resolve(server)));
}

async function loadPlaywright() {
  const candidates = [
    path.join(REPO_ROOT, 'vendor', 'RongXinAI', 'node_modules', 'playwright'),
    path.join(REPO_ROOT, 'node_modules', 'playwright'),
  ];
  const { createRequire } = await import('node:module');
  const req = createRequire(import.meta.url);
  for (const candidate of candidates) {
    try {
      const mod = req(candidate);
      const chromium = mod.chromium ?? mod.default?.chromium;
      if (chromium) return chromium;
    } catch {
      /* try next */
    }
  }
  throw new Error(`playwright not found; tried ${candidates.join(', ')}`);
}

const failures = [];
function fail(msg) {
  failures.push(msg);
  console.error(`[mobile-e2e] FAIL: ${msg}`);
}
function ok(msg) {
  console.log(`[mobile-e2e] OK:   ${msg}`);
}

async function main() {
  const server = await startServer();
  let chromium;
  try {
    chromium = await loadPlaywright();
  } catch (err) {
    server.close();
    console.error(err.message);
    process.exit(2);
  }

  const browser = await chromium.launch({ headless: true });
  try {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await ctx.newPage();

    const consoleErrors = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') consoleErrors.push(msg.text());
    });

    // Static checks: manifest + service worker reachable even without a built bundle.
    const manifestRes = await page.request.get(`http://127.0.0.1:${PORT}/manifest.webmanifest`);
    if (manifestRes.status() === 200) ok('manifest.webmanifest reachable');
    else fail(`manifest.webmanifest returned ${manifestRes.status()}`);

    const swRes = await page.request.get(`http://127.0.0.1:${PORT}/service-worker.js`);
    if (swRes.status() === 200) ok('service-worker.js reachable');
    else fail(`service-worker.js returned ${swRes.status()}`);

    const manifest = manifestRes.ok() ? await manifestRes.json() : null;
    if (manifest?.name === '熊宝 Agent') ok('manifest.name is 熊宝 Agent');
    else fail(`manifest.name was ${manifest?.name}`);
    if (manifest?.start_url === './') ok('manifest.start_url is ./');
    else fail(`manifest.start_url was ${manifest?.start_url}`);

    const htmlRes = await page.request.get(`http://127.0.0.1:${PORT}/index.html`);
    if (htmlRes.status() === 200) ok('index.html reachable');
    else fail(`index.html returned ${htmlRes.status()}`);
    const html = await htmlRes.text();
    if (html.includes('<html lang="zh-CN"')) ok('html lang=zh-CN');
    else fail('missing lang=zh-CN');
    if (html.includes('rel="manifest"')) ok('manifest link present');
    else fail('missing manifest link');
    if (html.includes('viewport-fit=cover')) ok('viewport-fit=cover set');
    else fail('missing viewport-fit=cover');

    // React app boot — only run if a built bundle is present (mobile/dist/assets/*.js).
    const hasBuiltBundle = fs.existsSync(
      path.join(MOBILE_ROOT, 'dist', 'assets'),
    );
    if (!hasBuiltBundle) {
      console.log(
        '[mobile-e2e] skipped React-boot checks (mobile/dist/ not built; run `bun run build` in mobile/ to enable them)',
      );
    } else {
      await page.goto(`http://127.0.0.1:${PORT}/`, { waitUntil: 'load' });
      const brand = await page.locator('.brand h1').first().textContent({ timeout: 5000 });
      if ((brand ?? '').includes('熊宝')) ok('brand renders');
      else fail(`brand missing, got "${brand}"`);

      await page.fill('input[autocomplete="url"]', 'http://127.0.0.1:1');
      await page.fill('input[autocomplete="username"]', 'tester');
      await page.fill('input[autocomplete="current-password"]', 'nopass');
      await page.click('button.primary');
      await page.waitForSelector('.error', { timeout: 10000 });
      ok('login shows error for unreachable backend');

      const fatal = consoleErrors.filter(
        (m) =>
          !m.includes('Failed to load resource') &&
          !m.includes('favicon') &&
          !m.includes('127.0.0.1:1'),
      );
      if (fatal.length === 0) ok('no fatal console errors');
      else fail(`console errors: ${fatal.join(' | ')}`);
    }
  } finally {
    await browser.close();
    server.close();
  }

  if (failures.length > 0) {
    console.error(`[mobile-e2e] ${failures.length} failure(s)`);
    process.exit(1);
  }
  console.log('[mobile-e2e] all checks passed');
}

main().catch((err) => {
  console.error('[mobile-e2e] crashed:', err);
  process.exit(1);
});
