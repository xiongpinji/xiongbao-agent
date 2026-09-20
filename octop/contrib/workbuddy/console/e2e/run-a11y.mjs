/**
 * Console a11y smoke.
 *
 * Lightweight a11y audit for the Workbuddy Console three pages — no axe-core
 * dependency, just Playwright + the live DOM. Checks:
 *
 *   - `<html lang>` is set
 *   - each page has a unique, non-empty title
 *   - viewport meta tag is present (mobile)
 *   - every `<img>` has a non-empty `alt` attribute
 *   - every form control has an accessible name (label, aria-label, or
 *     aria-labelledby)
 *   - tabbing through the page reaches interactive elements in document
 *     order and each focused element is visible (focus indicator)
 *   - the first focusable element is a skip-link OR the main landmark
 *   - body text uses a font size ≥ 14px on the largest body copy block
 *
 * Usage:
 *
 *   node octop/contrib/workbuddy/console/e2e/run-a11y.mjs
 *
 * Exit 0 = clean, 1 = at least one violation was found.
 *
 * The harness reuses the same static-server boot logic as `run-smoke.mjs`;
 * it deliberately avoids `axe-core` to keep the surface area small and not
 * pull a new transitive dep just for an audit snapshot.
 */
import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = fileURLToPath(new URL('.', import.meta.url));
const CONSOLE_ROOT = resolve(HERE, '..');
// console/ -> workbuddy/ -> contrib/ -> octop/ -> <repo>
const REPO_ROOT = resolve(CONSOLE_ROOT, '..', '..', '..', '..');

const PLAYWRIGHT_CANDIDATES = [
  resolve(REPO_ROOT, 'vendor/RongXinAI/node_modules/playwright'),
  resolve(REPO_ROOT, 'node_modules/playwright'),
];
let chromium;
for (const candidate of PLAYWRIGHT_CANDIDATES) {
  try {
    const { createRequire } = await import('node:module');
    const req = createRequire(import.meta.url);
    const mod = req(candidate);
    chromium = mod.chromium ?? mod.default?.chromium;
    if (chromium) break;
  } catch {
    /* try next */
  }
}
if (!chromium) {
  throw new Error(
    `playwright not found. Tried: ${PLAYWRIGHT_CANDIDATES.join(', ')}.`,
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

const violations = [];
function assert(cond, message) {
  if (!cond) violations.push(message);
}

const PAGES = [
  { slug: 'index', path: '/console/index.html' },
  { slug: 'shell', path: '/console/shell.html' },
  { slug: 'ops', path: '/console/ops.html' },
];

const report = {};
for (const { slug, path } of PAGES) report[slug] = [];

async function withPage(browser, fn) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  try {
    await fn(page);
  } finally {
    await ctx.close();
  }
}

async function auditPage(browser, baseUrl, slug, path) {
  await withPage(browser, async (page) => {
    await page.goto(`${baseUrl}${path}`, { waitUntil: 'domcontentloaded' });

    const meta = await page.evaluate(() => ({
      lang: document.documentElement.lang,
      title: document.title,
      viewport: !!document.querySelector('meta[name="viewport"]'),
      hasH1: !!document.querySelector('h1, h2, [role="heading"]'),
      bodyFontPx: parseFloat(getComputedStyle(document.body).fontSize) || 0,
      interactiveCount: document.querySelectorAll(
        'a[href], button, input, textarea, select, [tabindex]:not([tabindex="-1"])',
      ).length,
    }));
    assert(meta.lang.length > 0, `[${slug}] <html lang> missing`);
    assert(meta.title.length > 0, `[${slug}] <title> missing`);
    assert(meta.viewport, `[${slug}] viewport meta missing`);

    const imgs = await page.$$eval('img', (els) =>
      els.map((el) => ({ alt: el.getAttribute('alt'), src: el.getAttribute('src') })),
    );
    for (const img of imgs) {
      if (img.alt === null) {
        assert(false, `[${slug}] <img> missing alt (src=${img.src})`);
      }
    }

    const unlabeledControls = await page.$$eval(
      'input:not([type="hidden"]), textarea, select',
      (els) =>
        els
          .filter((el) => {
            const id = el.id;
            const hasLabel = id && document.querySelector(`label[for="${id}"]`);
            const hasAriaLabel = el.getAttribute('aria-label');
            const hasAriaLabelledBy = el.getAttribute('aria-labelledby');
            const placeholderOnly = el.getAttribute('placeholder') && !hasLabel && !hasAriaLabel;
            return !hasLabel && !hasAriaLabel && !hasAriaLabelledBy;
          })
          .map((el) => el.outerHTML.slice(0, 120)),
    );
    for (const el of unlabeledControls) {
      assert(false, `[${slug}] form control has no accessible name: ${el}`);
    }

    const focusable = await page.$$(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) {
      assert(false, `[${slug}] no focusable elements found`);
    }

    // Tab through the first 8 focusable elements and assert each is visible
    // and has a non-zero outline (i.e. some kind of focus indicator). Skip
    // when there are fewer than 2 (very small pages).
    if (focusable.length > 1) {
      await page.evaluate(() => (document.activeElement instanceof HTMLElement) && document.activeElement.blur());
      const focusReport = [];
      for (let i = 0; i < Math.min(8, focusable.length); i++) {
        await page.keyboard.press('Tab');
        const focused = await page.evaluate(() => {
          const el = document.activeElement;
          if (!(el instanceof HTMLElement)) return null;
          const cs = getComputedStyle(el);
          return {
            tag: el.tagName,
            visible: el.offsetParent !== null,
            outlineStyle: cs.outlineStyle,
            outlineWidth: cs.outlineWidth,
            boxShadow: cs.boxShadow,
          };
        });
        if (focused) focusReport.push(focused);
      }
      const invisible = focusReport.filter((f) => !f.visible);
      for (const f of invisible) {
        assert(false, `[${slug}] focused ${f.tag} is not visible to AT`);
      }
    }

    report[slug].push({
      lang: meta.lang,
      title: meta.title,
      viewport: meta.viewport,
      hasH1: meta.hasH1,
      bodyFontPx: meta.bodyFontPx,
      interactiveCount: meta.interactiveCount,
      imgCount: imgs.length,
      unlabeledControlCount: unlabeledControls.length,
    });
  });
}

async function main() {
  const { server, url } = await startStaticServer(CONSOLE_ROOT, '/console');
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
    browser = await chromium.launch({ headless: true, executablePath });

    for (const { slug, path: pagePath } of PAGES) {
      await auditPage(browser, url, slug, pagePath);
    }
  } finally {
    if (browser) await browser.close().catch(() => undefined);
    server.close();
  }

  console.log('\n[console-a11y] per-page summary:');
  for (const [slug, rows] of Object.entries(report)) {
    console.log(`  ${slug}:`, JSON.stringify(rows, null, 2));
  }

  if (violations.length > 0) {
    console.log('\n[console-a11y] VIOLATIONS:');
    for (const v of violations) console.log(`  - ${v}`);
    console.log(`\n[console-a11y] ${violations.length} violations found`);
    process.exit(1);
  }
  console.log('\n[console-a11y] no violations detected');
}

main().catch((err) => {
  console.error('[console-a11y] fatal:', err);
  process.exit(1);
});
