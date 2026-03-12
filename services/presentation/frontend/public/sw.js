/* Intentionally minimal service worker placeholder.
   Prevents browsers with stale registrations from fetching HTML at /sw.js. */
self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', () => {
  // no-op
});
