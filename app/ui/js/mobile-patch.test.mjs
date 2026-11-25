import assert from "node:assert/strict";
import test from "node:test";

const stored = new Map();
Object.defineProperty(globalThis, "localStorage", {
  configurable: true,
  value: {
    getItem: (key) => stored.get(key) ?? null,
    setItem: (key, value) => stored.set(key, value),
    removeItem: (key) => stored.delete(key)
  }
});

const { CommonPatch } = await import("./common-patch.js");
const { createRouterMethods02 } = await import("./ui/navigation/routerMethods-02-complete-route-return-back-guard.js");

function replaceGlobal(name, value) {
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, name);
  Object.defineProperty(globalThis, name, { configurable: true, value });
  return () => {
    if (descriptor) {
      Object.defineProperty(globalThis, name, descriptor);
    } else {
      delete globalThis[name];
    }
  };
}

test("shared fullscreen preserves ownership until cleanup", async () => {
  const orientationCalls = [];
  const orientation = {
    type: "portrait-primary",
    async lock(type) {
      orientationCalls.push(type);
      this.type = type === "landscape" ? "landscape-primary" : type;
    },
    unlock() {
      orientationCalls.push("unlock");
      assert.equal(documentObject.fullscreenElement, null);
      this.type = "portrait-primary";
    }
  };
  const documentObject = {
    fullscreenElement: null,
    addEventListener() {},
    removeEventListener() {},
    getElementById() {
      return null;
    },
    async exitFullscreen() {
      this.fullscreenElement = null;
    }
  };
  const restoreMatchMedia = replaceGlobal("matchMedia", () => ({ matches: true }));
  const restoreDocument = replaceGlobal("document", documentObject);
  const restoreScreen = replaceGlobal("screen", { orientation });
  const target = {
    async requestFullscreen() {
      documentObject.fullscreenElement = target;
      orientation.type = "landscape-primary";
    }
  };

  try {
    assert.equal(await CommonPatch.enterPlayerFullscreen(target), true);
    assert.equal(await CommonPatch.enterPlayerFullscreen(target), true);
    await CommonPatch.exitPlayerFullscreen();
    assert.equal(documentObject.fullscreenElement, null);
    assert.deepEqual(orientationCalls, ["landscape", "landscape", "unlock"]);
    assert.equal(globalThis.screen.orientation.type, "portrait-primary");
  } finally {
    await CommonPatch.exitPlayerFullscreen();
    restoreScreen();
    restoreDocument();
    restoreMatchMedia();
  }
});

test("parallel app and player fullscreen requests share one app-shell request", async () => {
  let resolveFullscreenRequest;
  let requestCount = 0;
  const documentObject = {
    fullscreenElement: null,
    addEventListener() {},
    removeEventListener() {},
    getElementById(id) {
      return id === "app" ? app : null;
    },
    async exitFullscreen() {
      this.fullscreenElement = null;
    }
  };
  const app = {
    requestFullscreen() {
      requestCount += 1;
      return new Promise((resolve) => {
        resolveFullscreenRequest = () => {
          documentObject.fullscreenElement = app;
          resolve();
        };
      });
    }
  };
  const player = {
    requestFullscreen() {
      assert.fail("fullscreen must stay on the app shell");
    }
  };
  const restoreMatchMedia = replaceGlobal("matchMedia", () => ({ matches: true }));
  const restoreDocument = replaceGlobal("document", documentObject);
  const restoreScreen = replaceGlobal("screen", {
    orientation: { async lock() {}, unlock() {} }
  });

  try {
    const appRequest = CommonPatch.enterPlayerFullscreen(app);
    const playerRequest = CommonPatch.enterPlayerFullscreen(player);
    assert.equal(requestCount, 1);
    resolveFullscreenRequest();
    assert.deepEqual(await Promise.all([appRequest, playerRequest]), [true, true]);
    await CommonPatch.exitPlayerFullscreen();
    assert.equal(documentObject.fullscreenElement, null);
  } finally {
    await CommonPatch.exitPlayerFullscreen();
    restoreScreen();
    restoreDocument();
    restoreMatchMedia();
  }
});

test("player exit does not wait for a pending landscape lock", async () => {
  let rejectLandscapeLock;
  let exitCount = 0;
  let unlockCount = 0;
  const documentObject = {
    fullscreenElement: null,
    addEventListener() {},
    removeEventListener() {},
    getElementById(id) {
      return id === "app" ? app : null;
    },
    async exitFullscreen() {
      exitCount += 1;
      this.fullscreenElement = null;
    }
  };
  const app = {
    async requestFullscreen() {
      documentObject.fullscreenElement = app;
    }
  };
  const orientation = {
    lock() {
      return new Promise((resolve, reject) => {
        rejectLandscapeLock = reject;
      });
    },
    unlock() {
      unlockCount += 1;
      rejectLandscapeLock?.(Object.assign(new Error("Lock cancelled"), { name: "AbortError" }));
    }
  };
  const restoreMatchMedia = replaceGlobal("matchMedia", () => ({ matches: true }));
  const restoreDocument = replaceGlobal("document", documentObject);
  const restoreScreen = replaceGlobal("screen", { orientation });

  try {
    assert.equal(await CommonPatch.enterPlayerFullscreen(app), true);
    await CommonPatch.exitPlayerFullscreen();
    assert.equal(exitCount, 1);
    assert.equal(unlockCount, 1);
    assert.equal(documentObject.fullscreenElement, null);
  } finally {
    await CommonPatch.exitPlayerFullscreen();
    restoreScreen();
    restoreDocument();
    restoreMatchMedia();
  }
});

test("browser-driven exit unlocks orientation even if the landscape lock rejected", async () => {
  let fullscreenChangeHandler;
  let unlockCount = 0;
  const documentObject = {
    fullscreenElement: null,
    addEventListener(name, handler) {
      if (name === "fullscreenchange") fullscreenChangeHandler = handler;
    },
    removeEventListener() {},
    getElementById(id) {
      return id === "app" ? app : null;
    }
  };
  const orientation = {
    type: "portrait-primary",
    async lock(type) {
      if (type === "landscape") {
        this.type = "landscape-primary";
        throw new Error("orientation lock rejected");
      }
    },
    unlock() {
      unlockCount += 1;
      this.type = "portrait-primary";
    }
  };
  const app = {
    async requestFullscreen() {
      documentObject.fullscreenElement = app;
    }
  };
  const restoreMatchMedia = replaceGlobal("matchMedia", () => ({ matches: true }));
  const restoreDocument = replaceGlobal("document", documentObject);
  const restoreScreen = replaceGlobal("screen", { orientation });
  const originalWarn = console.warn;
  console.warn = () => {};

  try {
    assert.equal(await CommonPatch.enterPlayerFullscreen(app), true);
    documentObject.fullscreenElement = null;
    fullscreenChangeHandler();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(unlockCount, 1);
    assert.equal(orientation.type, "portrait-primary");
  } finally {
    await CommonPatch.exitPlayerFullscreen();
    console.warn = originalWarn;
    restoreScreen();
    restoreDocument();
    restoreMatchMedia();
  }
});

test("stream auto-play fullscreen follows the loading-overlay eligibility", () => {
  const manualSettings = {
    streamAutoPlayMode: "MANUAL",
    streamReuseLastLinkEnabled: false,
    streamAutoPlayPreferBingeGroupForNextEpisode: false,
    streamAutoPlayReuseBingeGroup: false
  };
  const autoSettings = { ...manualSettings, streamAutoPlayMode: "FIRST_STREAM" };

  assert.equal(CommonPatch.shouldStartStreamAutoPlayLoadingOverlay({}, manualSettings), false);
  assert.equal(CommonPatch.shouldStartStreamAutoPlayLoadingOverlay({}, autoSettings), true);
  assert.equal(CommonPatch.shouldStartStreamAutoPlayLoadingOverlay({ manualSelection: true }, autoSettings), false);
});

test("stream and player routes enter fullscreen at the appropriate loading stage", async () => {
  const originalEnterFullscreen = CommonPatch.enterPlayerFullscreen;
  const originalExitFullscreen = CommonPatch.exitPlayerFullscreen;
  const originalShouldStartStreamAutoPlayLoadingOverlay =
    CommonPatch.shouldStartStreamAutoPlayLoadingOverlay;
  const app = {};
  const player = { style: { display: "none" } };
  const restoreDocument = replaceGlobal("document", {
    getElementById(id) {
      return id === "app" ? app : player;
    }
  });
  const restoreWindow = replaceGlobal("window", {
    history: {
      pushState() {},
      replaceState() {}
    }
  });
  const calls = [];
  CommonPatch.shouldStartStreamAutoPlayLoadingOverlay = (params) => params?.autoLoading === true;
  CommonPatch.enterPlayerFullscreen = (target) => {
    assert.equal(target, app);
    calls.push(`fullscreen:${router.current}`);
  };
  CommonPatch.exitPlayerFullscreen = () => {
    calls.push(`exit:${router.current}`);
  };
  const router = Object.assign(
    {
      routes: {
        stream: {
          mount() {
            calls.push("stream-mount");
          },
          cleanup() {}
        },
        player: {
          mount() {
            calls.push("player-mount");
          }
        },
        home: {
          mount() {}
        }
      },
      stack: [],
      captureCurrentRouteState() {},
      getCurrent() {
        return this.current;
      },
      beginRouteReturnBackGuard: () => 1,
      resolveNavigationContext: () => ({}),
      completeRouteReturnBackGuard() {},
      persistWebOsResumeRoute() {}
    },
    createRouterMethods02()
  );
  CommonPatch.installRouterNavigationPatch(router);

  try {
    await router.navigate("stream", { autoLoading: false });
    await router.navigate("player");
    await router.navigate("stream", { autoLoading: true });
    await router.navigate("home");
    await router.navigate("stream", { autoLoading: true });
    assert.deepEqual(calls, [
      "stream-mount",
      "fullscreen:stream",
      "player-mount",
      "stream-mount",
      "exit:stream",
      "fullscreen:home",
      "stream-mount"
    ]);
  } finally {
    CommonPatch.enterPlayerFullscreen = originalEnterFullscreen;
    CommonPatch.exitPlayerFullscreen = originalExitFullscreen;
    CommonPatch.shouldStartStreamAutoPlayLoadingOverlay =
      originalShouldStartStreamAutoPlayLoadingOverlay;
    restoreWindow();
    restoreDocument();
  }
});
