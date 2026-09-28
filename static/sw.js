/* PolyView Service Worker
   Strategy:
   - App shell (HTML, manifest) → Cache First
   - /api/*  → Network Only  (data selalu fresh dari server)
   - CDN scripts → Cache First (Three.js dll)
*/

const CACHE = 'polyview-v1';
const SHELL = ['/', '/index.html', '/manifest.json'];

/* ── Install: pre-cache shell ── */
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

/* ── Activate: remove old caches ── */
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

/* ── Fetch ── */
self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);

  // /api/* → selalu ke network (jangan cache data file)
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(fetch(e.request));
    return;
  }

  // CDN (Three.js, FBXLoader, fflate) → cache first
  if (url.origin !== location.origin) {
    e.respondWith(
      caches.open(CACHE).then(c =>
        c.match(e.request).then(cached => {
          if (cached) return cached;
          return fetch(e.request).then(res => {
            if (res.ok) c.put(e.request, res.clone());
            return res;
          }).catch(() => cached);
        })
      )
    );
    return;
  }

  // App shell → cache first, fallback network
  e.respondWith(
    caches.open(CACHE).then(c =>
      c.match(e.request).then(cached =>
        cached || fetch(e.request).then(res => {
          if (res.ok) c.put(e.request, res.clone());
          return res;
        })
      )
    )
  );
});
