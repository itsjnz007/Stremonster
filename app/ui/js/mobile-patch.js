const MOBILE_RUNTIME_PATCHED = Symbol("mobile-patch-runtime-patched");
const PORTRAIT_QUERY = "(orientation: portrait)";
const MOBILE_POINTER_QUERY = "(max-width: 950px) and (pointer: coarse)";
const MOBILE_LANDSCAPE_QUERY =
  "(orientation: landscape) and (max-height: 600px) and (pointer: coarse)";

let playerOrientationLockAttempted = false;

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

function restorePlayerOrientation() {
  if (!playerOrientationLockAttempted) {
    return;
  }
  playerOrientationLockAttempted = false;

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

  lockPlayerOrientation() {
    if (!isMobileDevice()) {
      return false;
    }

    const orientation = globalThis.screen?.orientation;
    if (typeof orientation?.lock !== "function") {
      return false;
    }

    playerOrientationLockAttempted = true;
    try {
      Promise.resolve(orientation.lock("landscape")).catch((error) => {
        if (error?.name !== "AbortError") {
          console.warn("Unable to lock player orientation to landscape", error);
        }
      });
    } catch (error) {
      if (error?.name !== "AbortError") {
        console.warn("Unable to lock player orientation to landscape", error);
      }
    }
    return true;
  },

  restorePlayerOrientation() {
    restorePlayerOrientation();
  }
};
