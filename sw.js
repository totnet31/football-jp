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

// Push通知受信
self.addEventListener('push', (event) => {
  if (!event.data) return;
  let payload;
  try {
    payload = event.data.json();
  } catch (e) {
    payload = { title: 'football-jp', body: event.data.text() };
  }
  const title = payload.title || 'football-jp';
  const options = {
    body: payload.body || '',
    icon: '/assets/logos/favicon-192.png',
    badge: '/assets/logos/favicon-192.png',
    tag: payload.tag || 'football-jp-default',
    data: { url: payload.url || '/' },
    requireInteraction: false
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

// 通知クリック
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if (w.url.includes(url) && 'focus' in w) return w.focus();
      }
      return clients.openWindow(url);
    })
  );
});
