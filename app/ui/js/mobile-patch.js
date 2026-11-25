const MOBILE_RUNTIME_PATCHED = Symbol("mobile-patch-runtime-patched");
const PORTRAIT_QUERY = "(orientation: portrait)";
const MOBILE_POINTER_QUERY = "(max-width: 950px) and (pointer: coarse)";
const MOBILE_LANDSCAPE_QUERY =
  "(orientation: landscape) and (max-height: 600px) and (pointer: coarse)";

let playerFullscreenTarget = null;
let playerOwnsFullscreen = false;
let playerOrientationLocked = false;
let fullscreenChangeHandler = null;

function isPortrait() {
  const mediaQuery = globalThis.matchMedia?.(PORTRAIT_QUERY);
  if (mediaQuery) {
    return mediaQuery.matches;
  }

  const width = Number(globalThis.innerWidth || document.documentElement?.clientWidth || 0);
  const height = Number(globalThis.innerHeight || document.documentElement?.clientHeight || 0);
  return width > 0 && height >= width;
}

function isMobileDevice() {
  const mediaQuery = globalThis.matchMedia?.(MOBILE_POINTER_QUERY);
  const landscapeQuery = globalThis.matchMedia?.(MOBILE_LANDSCAPE_QUERY);
  if (mediaQuery?.matches || landscapeQuery?.matches) {
    return true;
  }

  const touchPoints = Number(globalThis.navigator?.maxTouchPoints || 0);
  const isStandalone =
    globalThis.navigator?.standalone === true ||
    globalThis.matchMedia?.("(display-mode: standalone)")?.matches ||
    globalThis.matchMedia?.("(display-mode: minimal-ui)")?.matches;
  if (isStandalone && touchPoints > 0) {
    return true;
  }

  const width = Number(globalThis.innerWidth || 0);
  const height = Number(globalThis.innerHeight || 0);
  const isNarrowTouchDevice = width > 0 && width <= 950;
  const isShortLandscapeTouchDevice = width > height && height > 0 && height <= 600;
  return touchPoints > 0 && (isNarrowTouchDevice || isShortLandscapeTouchDevice);
}

function isFullscreenTarget(documentObject, target) {
  return (
    documentObject?.fullscreenElement === target ||
    documentObject?.webkitFullscreenElement === target
  );
}

function moveUniversalBackButtonToFullscreenTarget(documentObject, target) {
  const backButton = documentObject?.getElementById?.("universalBackButton");
  if (backButton && target?.append && backButton.parentNode !== target) {
    target.append(backButton);
  }
}

function restoreUniversalBackButtonToDocument(documentObject) {
  const backButton = documentObject?.getElementById?.("universalBackButton");
  const container = documentObject?.body || documentObject?.getElementById?.("app");
  if (backButton && container?.append && backButton.parentNode !== container) {
    container.append(backButton);
  }
}

function restorePlayerOrientation() {
  if (!playerOrientationLocked) {
    return;
  }
  playerOrientationLocked = false;

  const orientation = globalThis.screen?.orientation;
  try {
    orientation?.unlock?.();
  } catch (error) {
    console.warn("Unable to restore the previous player orientation", error);
  }
}

export const MobilePatch = {
  installRuntime() {
    if (this[MOBILE_RUNTIME_PATCHED]) {
      return;
    }
    this[MOBILE_RUNTIME_PATCHED] = true;

    const syncOrientation = () => {
      const root = document.documentElement;
      if (!root) {
        return;
      }

      const mobileDevice = isMobileDevice();
      const mobileOrientation = mobileDevice && isPortrait();
      root.classList.toggle("mobile-device", mobileDevice);
      root.classList.toggle("mobile-orientation", mobileOrientation);
    };
    const portraitQuery = globalThis.matchMedia?.(PORTRAIT_QUERY);
    const mobileQuery = globalThis.matchMedia?.(MOBILE_POINTER_QUERY);
    const mobileLandscapeQuery = globalThis.matchMedia?.(MOBILE_LANDSCAPE_QUERY);

    syncOrientation();
    if (typeof portraitQuery?.addEventListener === "function") {
      portraitQuery.addEventListener("change", syncOrientation);
    } else {
      portraitQuery?.addListener?.(syncOrientation);
    }
    if (typeof mobileQuery?.addEventListener === "function") {
      mobileQuery.addEventListener("change", syncOrientation);
    } else {
      mobileQuery?.addListener?.(syncOrientation);
    }
    if (typeof mobileLandscapeQuery?.addEventListener === "function") {
      mobileLandscapeQuery.addEventListener("change", syncOrientation);
    } else {
      mobileLandscapeQuery?.addListener?.(syncOrientation);
    }
    globalThis.addEventListener?.("resize", syncOrientation, { passive: true });
    globalThis.addEventListener?.("orientationchange", syncOrientation, { passive: true });
  },

  async enterPlayerFullscreen(target) {
    if (!isMobileDevice() || !target) {
      return false;
    }

    const documentObject = globalThis.document;
    if (!documentObject) {
      return false;
    }

    if (playerFullscreenTarget && playerFullscreenTarget !== target) {
      await this.exitPlayerFullscreen();
    }

    const alreadyManagingTarget = playerFullscreenTarget === target;
    const alreadyFullscreen = isFullscreenTarget(documentObject, target);
    if (!alreadyFullscreen) {
      const requestFullscreen = target.requestFullscreen || target.webkitRequestFullscreen;
      if (typeof requestFullscreen !== "function") {
        console.warn("Mobile player full screen is unavailable; landscape lock was skipped.");
        return false;
      }

      try {
        await requestFullscreen.call(target);
      } catch (error) {
        console.warn("Unable to enter mobile player full screen", error);
        return false;
      }
      if (!isFullscreenTarget(documentObject, target)) {
        console.warn("Mobile player did not enter full screen; landscape lock was skipped.");
        return false;
      }
    }

    playerFullscreenTarget = target;
    if (!alreadyFullscreen) {
      playerOwnsFullscreen = true;
    } else if (!alreadyManagingTarget) {
      playerOwnsFullscreen = false;
    }
    moveUniversalBackButtonToFullscreenTarget(documentObject, target);

    const orientation = globalThis.screen?.orientation;
    if (typeof orientation?.lock === "function") {
      try {
        await orientation.lock("landscape");
        playerOrientationLocked = true;
      } catch (error) {
        console.warn("Unable to lock player orientation to landscape", error);
      }
    }

    if (!fullscreenChangeHandler) {
      fullscreenChangeHandler = () => {
        if (playerFullscreenTarget && !isFullscreenTarget(documentObject, playerFullscreenTarget)) {
          restorePlayerOrientation();
          restoreUniversalBackButtonToDocument(documentObject);
        }
      };
      documentObject.addEventListener("fullscreenchange", fullscreenChangeHandler);
      documentObject.addEventListener("webkitfullscreenchange", fullscreenChangeHandler);
    }
    return true;
  },

  async exitPlayerFullscreen() {
    const documentObject = globalThis.document;
    const target = playerFullscreenTarget;
    const shouldExitFullscreen = playerOwnsFullscreen && isFullscreenTarget(documentObject, target);

    if (fullscreenChangeHandler) {
      documentObject?.removeEventListener("fullscreenchange", fullscreenChangeHandler);
      documentObject?.removeEventListener("webkitfullscreenchange", fullscreenChangeHandler);
      fullscreenChangeHandler = null;
    }

    if (shouldExitFullscreen) {
      const exitFullscreen = documentObject.exitFullscreen || documentObject.webkitExitFullscreen;
      if (typeof exitFullscreen === "function") {
        try {
          await exitFullscreen.call(documentObject);
        } catch (error) {
          console.warn("Unable to exit mobile player full screen", error);
        }
      }
    }

    restorePlayerOrientation();
    if (target && !isFullscreenTarget(documentObject, target)) {
      restoreUniversalBackButtonToDocument(documentObject);
    }
    playerFullscreenTarget = null;
    playerOwnsFullscreen = false;
  }
};
