/* Service worker for the 熊宝 Agent mobile PWA.
 *
 * Goals:
 *   1. Cache the application shell so cold-launch on flaky mobile networks
 *      still shows the login screen immediately.
 *   2. Never cache /api/* responses — auth tokens and chat history must
 *      always come from the network.
 *   3. Cache icons so the home-screen icon does not flash on first launch.
 */

const SHELL_CACHE = 'xiongbao-shell-v1';
const ICON_CACHE = 'xiongbao-icons-v1';
const SHELL_FILES = [
  './',
  './index.html',
  './manifest.webmanifest',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      await cache.addAll(SHELL_FILES);
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((k) => k !== SHELL_CACHE && k !== ICON_CACHE)
          .map((k) => caches.delete(k)),
      );
      await self.clients.claim();
    })(),
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // Never intercept API / WebSocket traffic.
  if (url.pathname.startsWith('/api/') || url.protocol === 'ws:' || url.protocol === 'wss:') {
    return;
  }

  // Icons: cache-first.
  if (url.pathname.startsWith('/mobile/icons/') || url.pathname.startsWith('./icons/')) {
    event.respondWith(cacheFirst(req, ICON_CACHE));
    return;
  }

  // App shell: network-first with cache fallback.
  event.respondWith(networkFirst(req, SHELL_CACHE));
});

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  try {
    const fresh = await fetch(request);
    if (fresh.ok) cache.put(request, fresh.clone());
    return fresh;
  } catch (err) {
    return new Response('', { status: 504, statusText: 'offline' });
  }
}

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const fresh = await fetch(request);
    if (fresh.ok) cache.put(request, fresh.clone());
    return fresh;
  } catch (err) {
    const cached = await cache.match(request);
    if (cached) return cached;
    return new Response('offline', { status: 504 });
  }
}
