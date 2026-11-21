import { NuvioDialog } from "./ui/components/nuvioDialog.js";

const COMMON_RUNTIME_PATCHED = Symbol("common-patch-runtime-patched");
const DIALOG_HOVER_PATCHED = Symbol("common-patch-dialog-hover-patched");

export const CommonPatch = {
  remotePageMinHeight: "100%",

  installWebAppShell() {
    const root = globalThis.document?.documentElement;
    if (!root) {
      return;
    }
    const standalone =
      globalThis.matchMedia?.("(display-mode: standalone)")?.matches ||
      globalThis.navigator?.standalone === true;
    root.classList.toggle("nuvio-pwa", Boolean(standalone));
    root.classList.toggle("nuvio-web-app", !/tizen|webos|smart-tv|hbbtv|netcast/i.test(
      globalThis.navigator?.userAgent || ""
    ));
  },

  installDialogHover(NuvioDialogClass) {
    const originalMount = NuvioDialogClass?.prototype?.mount;
    if (typeof originalMount !== "function" || originalMount[DIALOG_HOVER_PATCHED]) {
      return false;
    }

    const patchedMount = function (...args) {
      const result = originalMount.apply(this, args);
      this._buttonEls?.forEach((button, index) => {
        button.addEventListener("mouseenter", () => this._focusIndex(index));
      });
      return result;
    };
    patchedMount[DIALOG_HOVER_PATCHED] = true;
    NuvioDialogClass.prototype.mount = patchedMount;
    return true;
  },

  handleHomeCatalogContextMenu(event, Router) {
    const screen = Router.getCurrentScreen();
    const homeTarget = event?.target?.closest?.(".home-main .focusable");
    if (
      homeTarget &&
      screen?.container?.contains?.(homeTarget) &&
      screen.isHomeHoldTarget?.(homeTarget) &&
      typeof screen.openHoldMenuForNode === "function"
    ) {
      event.preventDefault();
      event.stopPropagation();
      screen.markUserInteractionSinceHomePaint();
      screen.openHoldMenuForNode(homeTarget);
      return true;
    }

    const catalogTarget = event?.target?.closest?.(
      ".seeall-card.focusable[data-action='openDetail']"
    );
    if (
      catalogTarget &&
      screen?.container?.contains?.(catalogTarget) &&
      screen.isPosterHoldTarget?.(catalogTarget) &&
      typeof screen.openPosterOptionsMenu === "function"
    ) {
      event.preventDefault();
      event.stopPropagation();
      void screen.openPosterOptionsMenu(catalogTarget);
      return true;
    }

    return false;
  },

  normalizeServerCapabilities(capabilities, { isCustom = false } = {}) {
    const browserEmailLogin = !isCustom && globalThis.__NUVIO_BROWSER_EMAIL_LOGIN__ === true;
    return {
      emailPasswordAuth: capabilities?.emailPasswordAuth === true || browserEmailLogin,
      tvLogin: capabilities?.tvLogin === true,
      watchParty: capabilities?.watchParty === true
    };
  },

  renderModernHomeStageMarkup({
    heroMarkup,
    catalogSections,
    continueWatchingItems,
    continueWatchingLoading,
    continueWatchingLoadingCount,
    continueWatchingRenderLimit,
    useEpisodeThumbnailsInCw,
    blurContinueWatchingNextUp,
    continueWatchingCardStyle,
    upcomingItems,
    posterSettings,
    renderContinueWatchingSection
  }) {
    return `
      <section class="home-modern-stage">
        <div class="home-modern-rows-viewport">
          <div class="home-modern-rows-scroll">
            ${heroMarkup}
            <div class="home-modern-rows-content">
              ${renderContinueWatchingSection(continueWatchingItems, {
                rowKey: "continue_watching",
                loading: continueWatchingLoading,
                loadingCount: continueWatchingLoadingCount,
                itemLimit: continueWatchingRenderLimit,
                useEpisodeThumbnails: useEpisodeThumbnailsInCw,
                blurNextUp: blurContinueWatchingNextUp,
                cardStyle: continueWatchingCardStyle,
                posterSettings
              })}
              ${renderContinueWatchingSection(upcomingItems, {
                rowKey: "upcoming_section",
                titleKey: "upcoming_section_title",
                title: "Upcoming",
                startIndex: continueWatchingItems.length,
                itemLimit: upcomingItems.length,
                useEpisodeThumbnails: useEpisodeThumbnailsInCw,
                blurNextUp: blurContinueWatchingNextUp,
                cardStyle: continueWatchingCardStyle,
                posterSettings
              })}
              <div class="home-modern-catalogs">
                ${catalogSections}
              </div>
            </div>
          </div>
        </div>
      </section>
    `;
  },

  clearPlayerFocusForHiddenControls(screen) {
    if (screen.isExternalFrameMode() || screen.controlsVisible || screen.isDialogOpen()) {
      return;
    }
    const root = screen.uiRefs?.root;
    const activeElement = document.activeElement;
    if (root && activeElement && root.contains(activeElement)) {
      activeElement.blur?.();
    }
  },

  onPlayerPointerMove(screen) {
    if (screen.pauseOverlayVisible && !screen.stillWatchingPromptVisible) {
      screen.dismissPauseOverlay({ revealControls: true, focus: false });
      return;
    }
    if (
      !screen.controlsVisible &&
      !screen.paused &&
      !screen.stillWatchingPromptVisible &&
      !screen.isExternalFrameMode() &&
      !screen.isDialogOpen() &&
      !screen.isStartupErrorVisible() &&
      !screen.isPostPlayVisible() &&
      !screen.loadingVisible
    ) {
      screen.setControlsVisible(true, { focus: false });
    }
  },

  onPlayerPointerSurfaceActivate(screen, target, original, args) {
    if (!target || screen.isExternalFrameMode()) {
      return false;
    }
    if (screen.pauseOverlayVisible) {
      if (screen.stillWatchingPromptVisible) {
        return false;
      }
      screen.dismissPauseOverlay({ revealControls: true, focus: false });
      return true;
    }
    return original.call(screen, target, ...args);
  },

  onPlayerPointerActivate(screen, target, original, args) {
    if (!target || screen.isExternalFrameMode()) {
      return false;
    }
    if (screen.pauseOverlayVisible && !screen.stillWatchingPromptVisible) {
      screen.dismissPauseOverlay({ revealControls: true, focus: false });
      return true;
    }
    return original.call(screen, target, ...args);
  },

  applyWebOsAspectMode(screen, video, Platform) {
    if (!video || !Platform.isWebOS() || Platform.isTizen()) {
      return;
    }
    const mode = screen.getAspectModeDefinition();
    const rect = screen.calculateAspectRect(mode.id, video);
    video.style.width = "100%";
    video.style.height = "100%";
    const stretchByObjectFit = mode.id === "STRETCH";
    video.style.transform =
      stretchByObjectFit || (rect.scaleX === 1 && rect.scaleY === 1)
        ? "none"
        : `scale(${rect.scaleX}, ${rect.scaleY})`;
  },

  installRuntime({ FocusEngine, PlayerScreen, Platform, Router }) {
    this.installWebAppShell();
    this.installDialogHover(NuvioDialog);
    if (this[COMMON_RUNTIME_PATCHED]) {
      return;
    }
    this[COMMON_RUNTIME_PATCHED] = true;

    const detailScreen = Router.routes?.detail;
    if (typeof detailScreen?.restartTrailerAutoplayTimer === "function") {
      detailScreen.restartTrailerAutoplayTimer = function disableTrailerAutoplay() {
        if (this.trailerAutoplayTimer) {
          clearTimeout(this.trailerAutoplayTimer);
          this.trailerAutoplayTimer = null;
        }
      };
    }

    document.addEventListener(
      "contextmenu",
      (event) => this.handleHomeCatalogContextMenu(event, Router),
      true
    );

    FocusEngine.requestBack = function requestBack() {
      if (Router.getCurrent() === "player") {
        const playerScreen = Router.getCurrentScreen();
        if (typeof playerScreen?.navigateBackToStreamScreen === "function") {
          return playerScreen.navigateBackToStreamScreen();
        }
      }

      return this.handleBack(null, {
        repeat: false,
        preventDefault() {},
        stopPropagation() {},
        stopImmediatePropagation() {}
      });
    };

    // Handle this before FocusEngine's async player pointer handler consumes the click.
    document.addEventListener(
      "click",
      (event) => {
        if (!event.target?.closest?.("#universalBackButton")) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
        FocusEngine.requestBack();
      },
      true
    );

    Router.syncUniversalBackButton = function syncUniversalBackButton() {
      const backButton = globalThis.document?.getElementById?.("universalBackButton");
      if (backButton) {
        backButton.hidden = ["home", "search", "settings", "library"].includes(this.current);
      }
    };
    for (const methodName of ["navigate", "back"]) {
      const original = Router[methodName];
      if (typeof original !== "function" || original[COMMON_RUNTIME_PATCHED]) {
        continue;
      }
      const patched = function (...args) {
        const result = original.apply(this, args);
        this.syncUniversalBackButton();
        return result;
      };
      patched[COMMON_RUNTIME_PATCHED] = true;
      Router[methodName] = patched;
    }

    let backButton = document.getElementById("universalBackButton");
    if (!backButton) {
      backButton = document.createElement("button");
      backButton.id = "universalBackButton";
      backButton.className = "universal-back-button focusable";
      backButton.type = "button";
      backButton.setAttribute("aria-label", "Back");
      backButton.innerHTML = '<span class="material-icons" aria-hidden="true">arrow_back</span>';
      document.getElementById("app")?.append(backButton);
    }
    backButton.hidden = true;

    const renderPlayerUi = PlayerScreen.renderPlayerUi;
    if (typeof renderPlayerUi === "function" && !renderPlayerUi[COMMON_RUNTIME_PATCHED]) {
      const patched = function (...args) {
        const result = renderPlayerUi.apply(this, args);
        this.uiRefs?.root?.removeAttribute?.("tabindex");
        return result;
      };
      patched[COMMON_RUNTIME_PATCHED] = true;
      PlayerScreen.renderPlayerUi = patched;
    }

    const applyAspectMode = PlayerScreen.applyAspectMode;
    if (typeof applyAspectMode === "function" && !applyAspectMode[COMMON_RUNTIME_PATCHED]) {
      const patched = function (...args) {
        const result = applyAspectMode.apply(this, args);
        const video =
          this.container?.querySelector?.("#videoPlayer") ||
          globalThis.document?.getElementById?.("videoPlayer");
        CommonPatch.applyWebOsAspectMode(this, video, Platform);
        return result;
      };
      patched[COMMON_RUNTIME_PATCHED] = true;
      PlayerScreen.applyAspectMode = patched;
    }

    const clearPlayerFocus = function clearPlayerFocus() {
      CommonPatch.clearPlayerFocusForHiddenControls(this);
    };
    PlayerScreen.focusPlayerRootForHiddenControls = clearPlayerFocus;
    PlayerScreen.clearPlayerFocusForHiddenControls = clearPlayerFocus;

    PlayerScreen.onPointerMove = function onPointerMove() {
      CommonPatch.onPlayerPointerMove(this);
    };

    const onPointerSurfaceActivate = PlayerScreen.onPointerSurfaceActivate;
    if (typeof onPointerSurfaceActivate === "function") {
      PlayerScreen.onPointerSurfaceActivate = function (target, ...args) {
        return CommonPatch.onPlayerPointerSurfaceActivate(
          this,
          target,
          onPointerSurfaceActivate,
          args
        );
      };
    }

    const onPointerActivate = PlayerScreen.onPointerActivate;
    if (typeof onPointerActivate === "function") {
      PlayerScreen.onPointerActivate = async function (target, ...args) {
        return CommonPatch.onPlayerPointerActivate(this, target, onPointerActivate, args);
      };
    }
  }
};
