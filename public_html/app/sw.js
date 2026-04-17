// sw.js — Service Worker для Dr. Gomon PWA
// CACHE_VERSION — оновлюй при кожному деплої (YYYY-MM-DD)
const CACHE = "gomon-2026-04-17h";
const STATIC = [
  '/app/index.html',
  '/app/gomon-chat.js',
  '/promos.php',
  '/app/manifest.json',
  'https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=Jost:wght@300;400;500&display=swap',
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(STATIC)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
     .then(() => self.clients.matchAll({includeUncontrolled: true}).then(cls => {
       cls.forEach(c => c.postMessage({type: 'sw-updated'}));
     }))
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // API запити — тільки мережа
  if (url.pathname.startsWith('/api/') || url.pathname.includes('chat.php')) {
    e.respondWith(fetch(e.request).catch(() =>
      new Response(JSON.stringify({error:'offline'}), {
        headers:{'Content-Type':'application/json'}
      })
    ));
    return;
  }

  // HTML — network first (щоб завжди отримувати свіжу версію)
  if (e.request.mode === 'navigate' || e.request.destination === 'document') {
    e.respondWith(
      fetch(e.request, {cache:"reload"}).catch(() => caches.match('/app/index.html'))
    );
    return;
  }

  // Тільки same-origin статика — cache first; зовнішні ресурси — network only
  if (url.origin !== self.location.origin || !url.protocol.startsWith("http")) {
    e.respondWith(fetch(e.request).catch(() => new Response("", {status: 408})));
    return;
  }

  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached;
      return fetch(e.request).then(response => {
        if (response.ok && response.status < 400) {
          try {
            const clone = response.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone).catch(() => {}));
          } catch(e) {}
        }
        return response;
      }).catch(() => caches.match("/app/index.html"));
    })
  );
});

// Push notifications
self.addEventListener('push', e => {
  const data = e.data ? e.data.json() : {};
  e.waitUntil(
    self.registration.showNotification(data.title || 'Dr. Gómon', {
      body: data.body || 'Нове повідомлення',
      icon: '/app/icons/icon-192-gomon.png',
      badge: '/app/icons/badge-white.png',
      tag: data.tag || 'gomon',
      data: data.url || '/app/',
      vibrate: [200, 100, 200],
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = e.notification.data || '/app/';
  // Only allow same-origin URLs
  const allowed = url.startsWith('/') || url.startsWith(self.location.origin);
  const safeUrl = allowed ? url : '/app/';
  const screen = safeUrl.includes('#') ? safeUrl.split('#')[1] : null;
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      const appClient = list.find(c => c.url.includes('/app/'));
      if (appClient) {
        if (screen) appClient.postMessage({ type: 'navigate', screen });
        return appClient.focus();
      }
      return clients.openWindow(safeUrl);
    })
  );
});
