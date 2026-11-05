import * as internals from "./playerScreenContext.js";

export function createPlayerScreenMethods75() {
  const { t } = internals;

  return {
    isMobileFullscreenTarget() {
      return typeof window !== "undefined" && window.matchMedia?.("(max-width: 700px) and (pointer: coarse)")?.matches === true;
    },
    isPlayerFullscreen() {
      const root = this.uiRefs?.root;
      return Boolean(root && (document.fullscreenElement === root || document.webkitFullscreenElement === root));
    },
    syncPlayerFullscreenButton() {
      const button = this.uiRefs?.fullscreenToggle;
      if (!button) {
        return;
      }
      const isFullscreen = this.isPlayerFullscreen();
      const label = isFullscreen
        ? t("player_exit_fullscreen", {}, "Exit full screen")
        : t("player_enter_fullscreen", {}, "Full screen");
      button.setAttribute("aria-label", label);
      button.title = label;
      const icon = button.querySelector(".material-icons");
      if (icon) {
        icon.textContent = isFullscreen ? "fullscreen_exit" : "fullscreen";
      }
    },
    async enterPlayerFullscreen({ lockLandscape = false } = {}) {
      const root = this.uiRefs?.root;
      if (!root || this.isPlayerFullscreen()) {
        if (lockLandscape) {
          await this.lockPlayerLandscape();
        }
        return this.isPlayerFullscreen();
      }
      const requestFullscreen = root.requestFullscreen || root.webkitRequestFullscreen;
      if (typeof requestFullscreen !== "function") {
        return false;
      }
      try {
        await requestFullscreen.call(root);
      } catch (error) {
        console.warn("Unable to enter player full screen", error);
        return false;
      }
      if (!this.isPlayerFullscreen()) {
        return false;
      }
      this.syncPlayerFullscreenButton();
      if (lockLandscape) {
        await this.lockPlayerLandscape();
      }
      return true;
    },
    async lockPlayerLandscape() {
      const orientation = globalThis.screen?.orientation;
      if (typeof orientation?.lock !== "function") {
        return false;
      }
      try {
        await orientation.lock("landscape");
        this.playerOrientationLocked = true;
        return true;
      } catch (error) {
        console.warn("Unable to lock player orientation to landscape", error);
        return false;
      }
    },
    restorePlayerOrientation() {
      if (!this.playerOrientationLocked) {
        return;
      }
      this.playerOrientationLocked = false;
      try {
        globalThis.screen?.orientation?.unlock?.();
      } catch (error) {
        console.warn("Unable to restore the previous player orientation", error);
      }
    },
    async togglePlayerFullscreen() {
      if (this.isPlayerFullscreen()) {
        const exitFullscreen = document.exitFullscreen || document.webkitExitFullscreen;
        if (typeof exitFullscreen === "function") {
          try {
            await exitFullscreen.call(document);
          } catch (error) {
            console.warn("Unable to exit player full screen", error);
          }
        }
        this.restorePlayerOrientation();
        this.syncPlayerFullscreenButton();
        return;
      }
      await this.enterPlayerFullscreen({ lockLandscape: this.isMobileFullscreenTarget() });
    },
    initializePlayerFullscreen() {
      this.playerOrientationLocked = false;
      this.playerFullscreenChangeHandler = () => {
        this.syncPlayerFullscreenButton();
        if (!this.isPlayerFullscreen()) {
          this.restorePlayerOrientation();
        }
      };
      document.addEventListener("fullscreenchange", this.playerFullscreenChangeHandler);
      document.addEventListener("webkitfullscreenchange", this.playerFullscreenChangeHandler);
      this.syncPlayerFullscreenButton();
      if (this.isMobileFullscreenTarget()) {
        void this.enterPlayerFullscreen({ lockLandscape: true });
      }
    },
    cleanupPlayerFullscreen() {
      if (this.playerFullscreenChangeHandler) {
        document.removeEventListener("fullscreenchange", this.playerFullscreenChangeHandler);
        document.removeEventListener("webkitfullscreenchange", this.playerFullscreenChangeHandler);
        this.playerFullscreenChangeHandler = null;
      }
      if (this.isPlayerFullscreen()) {
        const exitFullscreen = document.exitFullscreen || document.webkitExitFullscreen;
        if (typeof exitFullscreen === "function") {
          void Promise.resolve(exitFullscreen.call(document)).catch((error) => {
            console.warn("Unable to exit player full screen during cleanup", error);
          });
        }
      }
      this.restorePlayerOrientation();
    }
  };
}
