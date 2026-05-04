const CACHE_VERSION = 'v1';
const CACHE_NAME = `football-jp-${CACHE_VERSION}`;

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// network-first戦略（HTMLは常に最新、静的アセットはキャッシュフォールバック）
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  event.respondWith(
    fetch(req).then((res) => {
      // 200のみキャッシュ
      if (res.ok && (req.url.includes('/data/') || req.url.includes('/assets/'))) {
        const clone = res.clone();
        caches.open(CACHE_NAME).then(c => c.put(req, clone));
      }
      return res;
    }).catch(() => caches.match(req))
  );
});
