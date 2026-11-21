(function configureCommonPatch(root) {
  "use strict";

  if (!root.__NUVIO_ENV__ || typeof root.__NUVIO_ENV__ !== "object") {
    throw new Error("nuvio.env.js must load before common-patch.js");
  }

  root.__NUVIO_ENV__.NUVIO_SUPABASE_URL = "https://api.nuvio.tv";
  root.__NUVIO_ENV__.NUVIO_SUPABASE_ANON_KEY = "sb_publishable_1Clq8rlTVACkdcZuqr6_AD__xUUC_EN";

  var platform = String(root.__NUVIO_PLATFORM__ || "").toLowerCase();
  var userAgent = String((root.navigator && root.navigator.userAgent) || "").toLowerCase();
  var webapis = root.webapis || {};
  var isTv =
    platform === "tizen" ||
    platform === "webos" ||
    Boolean(
      root.tizen ||
        root.avplay ||
        webapis.avplay ||
        webapis.avPlay ||
        webapis.productinfo ||
        root.PalmSystem ||
        root.webOS ||
        root.webOSSystem ||
        /tizen|webos|web0s|smart[- ]?tv|hbbtv|netcast/.test(userAgent)
    );

  root.__NUVIO_BROWSER_EMAIL_LOGIN__ = !isTv;

  if (
    !isTv &&
    root.navigator &&
    "serviceWorker" in root.navigator &&
    root.isSecureContext
  ) {
    root.addEventListener?.("load", function registerNuvioServiceWorker() {
      root.navigator.serviceWorker.register("./service-worker.js").catch(function (error) {
        console.warn("Unable to register the Nuvio web app service worker", error);
      });
    });
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
