// Service worker del modo mozo (scope: /salon). Sin caché ni soporte offline
// a propósito — Restolibra es server-rendered y siempre necesita red para
// operar sobre el estado real de mesas/pedidos. Solo existe para que Chrome
// considere instalable la PWA.
self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
