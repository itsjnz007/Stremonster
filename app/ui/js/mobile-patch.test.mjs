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

const { MobilePatch } = await import("./mobile-patch.js");
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

test("re-entering fullscreen preserves player ownership until cleanup", async () => {
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
    assert.equal(await MobilePatch.enterPlayerFullscreen(target), true);
    assert.equal(await MobilePatch.enterPlayerFullscreen(target), true);
    await MobilePatch.exitPlayerFullscreen();
    assert.equal(documentObject.fullscreenElement, null);
    assert.deepEqual(orientationCalls, ["landscape", "landscape", "unlock"]);
    assert.equal(globalThis.screen.orientation.type, "portrait-primary");
  } finally {
    await MobilePatch.exitPlayerFullscreen();
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
    const appRequest = MobilePatch.enterPlayerFullscreen(app);
    const playerRequest = MobilePatch.enterPlayerFullscreen(player);
    assert.equal(requestCount, 1);
    resolveFullscreenRequest();
    assert.deepEqual(await Promise.all([appRequest, playerRequest]), [true, true]);
    await MobilePatch.exitPlayerFullscreen();
    assert.equal(documentObject.fullscreenElement, null);
  } finally {
    await MobilePatch.exitPlayerFullscreen();
    restoreScreen();
    restoreDocument();
    restoreMatchMedia();
  }
});

test("parallel exit requests share one fullscreen exit and orientation unlock", async () => {
  let resolveFullscreenExit;
  let exitCount = 0;
  let unlockCount = 0;
  const documentObject = {
    fullscreenElement: null,
    addEventListener() {},
    removeEventListener() {},
    getElementById(id) {
      return id === "app" ? app : null;
    },
    exitFullscreen() {
      exitCount += 1;
      return new Promise((resolve) => {
        resolveFullscreenExit = () => {
          this.fullscreenElement = null;
          resolve();
        };
      });
    }
  };
  const app = {
    async requestFullscreen() {
      documentObject.fullscreenElement = app;
    }
  };
  const restoreMatchMedia = replaceGlobal("matchMedia", () => ({ matches: true }));
  const restoreDocument = replaceGlobal("document", documentObject);
  const restoreScreen = replaceGlobal("screen", {
    orientation: {
      async lock() {},
      unlock() {
        unlockCount += 1;
      }
    }
  });

  try {
    assert.equal(await MobilePatch.enterPlayerFullscreen(app), true);
    const firstExit = MobilePatch.exitPlayerFullscreen();
    const secondExit = MobilePatch.exitPlayerFullscreen();
    assert.equal(exitCount, 1);
    resolveFullscreenExit();
    await Promise.all([firstExit, secondExit]);
    assert.equal(unlockCount, 1);
    assert.equal(documentObject.fullscreenElement, null);
  } finally {
    await MobilePatch.exitPlayerFullscreen();
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
    assert.equal(await MobilePatch.enterPlayerFullscreen(app), true);
    documentObject.fullscreenElement = null;
    fullscreenChangeHandler();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(unlockCount, 1);
    assert.equal(orientation.type, "portrait-primary");
  } finally {
    await MobilePatch.exitPlayerFullscreen();
    console.warn = originalWarn;
    restoreScreen();
    restoreDocument();
    restoreMatchMedia();
  }
});

test("stream and player routes share fullscreen before their screens mount", async () => {
  const originalEnterFullscreen = MobilePatch.enterPlayerFullscreen;
  const originalExitFullscreen = MobilePatch.exitPlayerFullscreen;
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
  MobilePatch.enterPlayerFullscreen = (target) => {
    assert.equal(target, app);
    calls.push(`fullscreen:${router.current}`);
  };
  MobilePatch.exitPlayerFullscreen = () => {
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
    await router.navigate("stream");
    await router.navigate("player");
    await router.navigate("stream");
    assert.deepEqual(calls, [
      "fullscreen:undefined",
      "stream-mount",
      "fullscreen:stream",
      "player-mount",
      "exit:player",
      "stream-mount"
    ]);
  } finally {
    MobilePatch.enterPlayerFullscreen = originalEnterFullscreen;
    MobilePatch.exitPlayerFullscreen = originalExitFullscreen;
    restoreWindow();
    restoreDocument();
  }
});
