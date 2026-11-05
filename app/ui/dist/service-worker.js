const BUILD_VERSION = "93ee25fb3c02";
const CACHE_NAME = `nuvio-tv-shell-${BUILD_VERSION}`;
const APP_SHELL = [
  "./",
  `./app.bundle.js?v=${BUILD_VERSION}`,
  "./boot-guard.js",
  "./core-js.bundle.js",
  "./nuvio.env.js",
  `./css/bundle.css?v=${BUILD_VERSION}`,
  "./assets/runtime/legacy-features.js",
  "./assets/libs/qrcode-generator.js"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) =>
        Promise.all(
          cacheNames
            .filter((cacheName) => cacheName.startsWith("nuvio-tv-shell-") && cacheName !== CACHE_NAME)
            .map((cacheName) => caches.delete(cacheName))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const requestUrl = new URL(request.url);
  const scopeUrl = new URL(self.registration.scope);
  const isAppNavigation = request.mode === "navigate" && requestUrl.origin === scopeUrl.origin;
  const isAppAsset =
    request.method === "GET" &&
    requestUrl.origin === scopeUrl.origin &&
    requestUrl.pathname.startsWith(scopeUrl.pathname) &&
    /\.(?:css|html|js|json|png|svg|webp|woff2?)$/i.test(requestUrl.pathname);

  if (!isAppNavigation && !isAppAsset) {
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const responseCopy = response.clone();
          return caches
            .open(CACHE_NAME)
            .then((cache) => cache.put(request, responseCopy))
            .then(() => response);
        }
        return response;
      })
      .catch(async () => {
        const cachedResponse = await caches.match(request, { ignoreSearch: true });
        if (cachedResponse) {
          return cachedResponse;
        }
        if (isAppNavigation) {
          return caches.match(new URL("./", scopeUrl).href);
        }
        return Response.error();
      })
  );
});
