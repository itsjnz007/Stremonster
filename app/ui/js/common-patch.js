import { NuvioDialog } from "./ui/components/nuvioDialog.js";
import { PlayerSettingsStore } from "./data/local/playerSettingsStore.js";
import { StreamPreferencesStore } from "./data/local/streamPreferencesStore.js";
import { isAutoPlayEffectivelyEnabled } from "./core/streams/streamAutoPlaySelector.js";
import { MobilePatch } from "./mobile-patch.js";

const COMMON_RUNTIME_PATCHED = Symbol("common-patch-runtime-patched");
const DIALOG_HOVER_PATCHED = Symbol("common-patch-dialog-hover-patched");

let playerFullscreenTarget = null;
let playerOwnsFullscreen = false;
let fullscreenChangeHandler = null;
let fullscreenEntryTarget = null;
let fullscreenEntryPromise = null;

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

function escapeHtml(value = "") {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function escapeAttribute(value = "") {
  return escapeHtml(value).replaceAll("'", "&#39;");
}

export const CommonPatch = {
  remotePageMinHeight: "100%",

  async enterPlayerFullscreen(target) {
    if (!target) {
      return false;
    }

    const documentObject = globalThis.document;
    if (!documentObject) {
      return false;
    }

    const fullscreenTarget = documentObject.getElementById?.("app") || target;
    if (fullscreenEntryPromise) {
      if (fullscreenEntryTarget === fullscreenTarget) {
        return fullscreenEntryPromise;
      }
      await fullscreenEntryPromise;
    }

    const operation = (async () => {
      if (playerFullscreenTarget && playerFullscreenTarget !== fullscreenTarget) {
        await this.exitPlayerFullscreen();
      }

      const alreadyManagingTarget = playerFullscreenTarget === fullscreenTarget;
      const alreadyFullscreen = isFullscreenTarget(documentObject, fullscreenTarget);
      if (!alreadyFullscreen) {
        const requestFullscreen =
          fullscreenTarget.requestFullscreen || fullscreenTarget.webkitRequestFullscreen;
        if (typeof requestFullscreen !== "function") {
          console.warn("Player full screen is unavailable.");
          return false;
        }

        try {
          await requestFullscreen.call(fullscreenTarget);
        } catch (error) {
          console.warn("Unable to enter player full screen", error);
          return false;
        }
        if (!isFullscreenTarget(documentObject, fullscreenTarget)) {
          console.warn("Player did not enter full screen.");
          return false;
        }
      }

      playerFullscreenTarget = fullscreenTarget;
      if (!alreadyFullscreen) {
        playerOwnsFullscreen = true;
      } else if (!alreadyManagingTarget) {
        playerOwnsFullscreen = false;
      }
      moveUniversalBackButtonToFullscreenTarget(documentObject, fullscreenTarget);

      if (!fullscreenChangeHandler) {
        fullscreenChangeHandler = () => {
          if (playerFullscreenTarget && !isFullscreenTarget(documentObject, playerFullscreenTarget)) {
            void this.exitPlayerFullscreen();
          }
        };
        documentObject.addEventListener("fullscreenchange", fullscreenChangeHandler);
        documentObject.addEventListener("webkitfullscreenchange", fullscreenChangeHandler);
      }

      MobilePatch.lockPlayerOrientation();
      return true;
    })();

    fullscreenEntryTarget = fullscreenTarget;
    fullscreenEntryPromise = operation;
    try {
      return await operation;
    } finally {
      if (fullscreenEntryPromise === operation) {
        fullscreenEntryTarget = null;
        fullscreenEntryPromise = null;
      }
    }
  },

  async exitPlayerFullscreen() {
    if (fullscreenEntryPromise) {
      await fullscreenEntryPromise;
    }

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
          console.warn("Unable to exit player full screen", error);
        }
      }
    }

    MobilePatch.restorePlayerOrientation();
    if (target && !isFullscreenTarget(documentObject, target)) {
      restoreUniversalBackButtonToDocument(documentObject);
    }
    playerFullscreenTarget = null;
    playerOwnsFullscreen = false;
  },

  renderPlayerLoadingOverlayMarkup({
    id = "playerLoadingOverlay",
    title = "",
    subtitle = "",
    logoUrl = "",
    backdropUrl = "",
    escapeHtml,
    escapeAttribute = escapeHtml
  } = {}) {
    const safeBackdropUrl = String(backdropUrl || "").replaceAll("'", "%27");
    return `
      <div${id ? ` id="${escapeAttribute(id)}"` : ""} class="player-loading-overlay">
        <div class="player-loading-backdrop"${safeBackdropUrl ? ` style="background-image:url('${escapeAttribute(safeBackdropUrl)}')"` : ""}></div>
        <div class="player-loading-gradient"></div>
        <div class="player-loading-center">
          <div class="player-loading-identity${logoUrl ? " has-logo" : ""}">
            ${
              logoUrl
                ? `
              <div class="player-loading-logo-stack">
                <img class="player-loading-logo player-loading-logo-base" src="${escapeAttribute(logoUrl)}" alt="${escapeAttribute(title || "logo")}" />
                <div class="player-loading-logo-fill-clip hidden">
                  <img class="player-loading-logo player-loading-logo-fill" src="${escapeAttribute(logoUrl)}" alt="" aria-hidden="true" />
                </div>
              </div>
            `
                : ""
            }
            <div class="player-loading-title">${escapeHtml(title || "Nuvio")}</div>
          </div>
          <div class="player-loading-subtitle${subtitle ? "" : " hidden"}">${escapeHtml(subtitle || "")}</div>
          <div class="player-loading-status hidden"></div>
        </div>
      </div>`;
  },

  shouldStartStreamAutoPlayLoadingOverlay(params = {}, settings = PlayerSettingsStore.get()) {
    const autoPlayMode = String(settings.streamAutoPlayMode || "MANUAL").toUpperCase();
    const savedPreference =
      settings.streamAutoPlayPreferBingeGroupForNextEpisode && settings.streamAutoPlayReuseBingeGroup
        ? StreamPreferencesStore.getLatestForContent(params?.itemId)
        : null;
    const hasPreferredBingeGroup = Boolean(String(savedPreference?.bingeGroup || "").trim());

    return Boolean(
      isAutoPlayEffectivelyEnabled(settings) &&
      !params?.manualSelection &&
      (autoPlayMode !== "MANUAL" || hasPreferredBingeGroup)
    );
  },

  shouldShowStreamAutoPlayLoadingOverlay(screen, settings = PlayerSettingsStore.get()) {
    return Boolean(
      !screen.autoResumeAttempted &&
      !screen.autoResumeUiActive &&
      this.shouldStartStreamAutoPlayLoadingOverlay(screen.params, settings) &&
      screen.loading &&
      !screen.streams?.length &&
      !screen.error
    );
  },

  syncStreamAutoPlayLoadingOverlay(screen, settings = PlayerSettingsStore.get()) {
    const shell = screen.container?.querySelector?.(".stream-route-shell");
    if (!shell) {
      return;
    }

    const showOverlay = this.shouldShowStreamAutoPlayLoadingOverlay(screen, settings);
    const routeContent = shell.querySelector?.(".stream-route-content");
    routeContent?.classList?.toggle("hidden", showOverlay);

    const overlay = shell.querySelector?.("#streamAutoPlayLoadingOverlay");
    if (!showOverlay) {
      overlay?.remove?.();
      return;
    }
    if (overlay) {
      return;
    }

    const { title, subtitle } = screen.getHeaderMeta();
    shell.insertAdjacentHTML?.(
      "beforeend",
      this.renderPlayerLoadingOverlayMarkup({
        id: "streamAutoPlayLoadingOverlay",
        title,
        subtitle,
        backdropUrl: screen.getBackdropUrl(),
        logoUrl: screen.params?.logo || "",
        escapeHtml,
        escapeAttribute
      })
    );
  },

  installStreamScreenPatch(screen) {
    const originalRender = screen?.render;
    if (typeof originalRender !== "function" || originalRender[COMMON_RUNTIME_PATCHED]) {
      return false;
    }

    const patchedRender = function (...args) {
      const result = originalRender.apply(this, args);
      CommonPatch.syncStreamAutoPlayLoadingOverlay(this);
      return result;
    };
    patchedRender[COMMON_RUNTIME_PATCHED] = true;
    screen.render = patchedRender;
    return true;
  },

  installRouterNavigationPatch(Router) {
    const originalNavigate = Router?.navigate;
    if (typeof originalNavigate !== "function" || originalNavigate[COMMON_RUNTIME_PATCHED]) {
      return false;
    }

    const patchedNavigate = function (...args) {
      const routeName = args[0];
      const previousRoute = this.getCurrent?.() || this.current;
      const startStreamAutoPlayLoading =
        routeName === "stream" &&
        previousRoute !== "player" &&
        CommonPatch.shouldStartStreamAutoPlayLoadingOverlay(args[1] || {});
      if (previousRoute === "stream" && routeName !== "player") {
        void CommonPatch.exitPlayerFullscreen();
      }
      if (routeName === "player" || startStreamAutoPlayLoading) {
        const app = globalThis.document?.getElementById?.("app");
        if (app) {
          void CommonPatch.enterPlayerFullscreen(app);
        }
      }

      const result = originalNavigate.apply(this, args);
      this.syncUniversalBackButton?.();
      return result;
    };
    patchedNavigate[COMMON_RUNTIME_PATCHED] = true;
    Router.navigate = patchedNavigate;
    return true;
  },

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
    if (String(Router.getCurrent?.() || "") === "detail") {
      return false;
    }
    const genericTarget = event?.target?.closest?.(".focusable");
    if (
      genericTarget &&
      screen?.container?.contains?.(genericTarget) &&
      typeof screen.isPosterHoldTarget === "function" &&
      screen.isPosterHoldTarget(genericTarget) &&
      typeof screen.openPosterOptionsMenu === "function"
    ) {
      event.preventDefault();
      event.stopPropagation();
      this.cancelPointerHold();
      this.suppressPointerHoldClick(genericTarget);
      void screen.openPosterOptionsMenu(genericTarget);
      return true;
    }

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
      this.cancelPointerHold();
      this.suppressPointerHoldClick(homeTarget);
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

  getPointerHoldTarget(event, Router) {
    const screen = Router.getCurrentScreen();
    if (!screen?.container) {
      return null;
    }
    if (String(Router.getCurrent?.() || "") === "detail") {
      return null;
    }
    const node = event?.target?.closest?.(".focusable");
    if (!node || !screen.container.contains(node)) {
      return null;
    }
    if (typeof screen.isPosterHoldTarget === "function" && screen.isPosterHoldTarget(node)) {
      if (typeof screen.openPosterOptionsMenu === "function") {
        return { screen, node, kind: "poster" };
      }
      if (typeof screen.openHoldMenuForNode === "function") {
        return { screen, node, kind: "home" };
      }
    }
    if (
      typeof screen.isHomeHoldTarget === "function" &&
      screen.isHomeHoldTarget(node) &&
      typeof screen.openHoldMenuForNode === "function"
    ) {
      return { screen, node, kind: "home" };
    }
    return null;
  },

  cancelPointerHold() {
    if (this._pointerHoldTimer) {
      clearTimeout(this._pointerHoldTimer);
      this._pointerHoldTimer = null;
    }
    this._pointerHold = null;
  },

  openPointerHoldMenu(hold) {
    if (hold.kind === "poster") {
      void hold.screen.openPosterOptionsMenu(hold.node);
      return;
    }
    hold.screen.openHoldMenuForNode(hold.node);
  },

  suppressPointerHoldClick(node) {
    if (this._pointerHoldClickTimer) {
      clearTimeout(this._pointerHoldClickTimer);
    }
    this._pointerHoldClickTarget = node;
    this._pointerHoldClickTimer = setTimeout(() => {
      this._pointerHoldClickTimer = null;
      this._pointerHoldClickTarget = null;
    }, 1200);
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
      !screen.isPostPlayVisible()
    ) {
      screen.setControlsVisible(true, { focus: false });
    }
  },

  onPlayerPointerSurfaceActivate(screen, target, original, args) {
    if (!target || screen.isExternalFrameMode()) {
      return false;
    }
    if (
      screen.loadingVisible &&
      !screen.controlsVisible &&
      !screen.stillWatchingPromptVisible &&
      !screen.isDialogOpen() &&
      !screen.isStartupErrorVisible() &&
      !screen.isPostPlayVisible()
    ) {
      screen.setControlsVisible(true, { focus: false });
      return true;
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
    this.installStreamScreenPatch(Router.routes?.stream);

    document.addEventListener(
      "contextmenu",
      (event) => this.handleHomeCatalogContextMenu(event, Router),
      true
    );

    document.addEventListener(
      "pointerdown",
      (event) => {
        if (event.button !== 0 || event.isPrimary === false) {
          return;
        }
        const hold = this.getPointerHoldTarget(event, Router);
        if (!hold) {
          this.cancelPointerHold();
          return;
        }
        this.cancelPointerHold();
        const pending = {
          ...hold,
          pointerId: event.pointerId,
          startX: Number(event.clientX),
          startY: Number(event.clientY),
          triggered: false
        };
        this._pointerHold = pending;
        this._pointerHoldTimer = setTimeout(() => {
          if (this._pointerHold !== pending || !pending.node.isConnected) {
            return;
          }
          this._pointerHoldTimer = null;
          pending.triggered = true;
          this.suppressPointerHoldClick(pending.node);
          this.openPointerHoldMenu(pending);
        }, 650);
      },
      true
    );

    document.addEventListener(
      "pointermove",
      (event) => {
        const pending = this._pointerHold;
        if (!pending || pending.triggered || event.pointerId !== pending.pointerId) {
          return;
        }
        const deltaX = Number(event.clientX) - pending.startX;
        const deltaY = Number(event.clientY) - pending.startY;
        if (Math.hypot(deltaX, deltaY) > 12) {
          this.cancelPointerHold();
        }
      },
      true
    );

    document.addEventListener(
      "pointerup",
      (event) => {
        const pending = this._pointerHold;
        if (!pending || event.pointerId !== pending.pointerId) {
          return;
        }
        this.cancelPointerHold();
      },
      true
    );

    document.addEventListener(
      "pointercancel",
      (event) => {
        const pending = this._pointerHold;
        if (!pending || event.pointerId !== pending.pointerId) {
          return;
        }
        this.cancelPointerHold();
      },
      true
    );

    document.addEventListener(
      "click",
      (event) => {
        const node = event?.target?.closest?.(".focusable");
        if (!node || node !== this._pointerHoldClickTarget) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
      },
      true
    );

    let universalBackButtonRequestScreen = null;
    const consumePlayerBackRequest = PlayerScreen.consumeBackRequest;
    if (
      typeof consumePlayerBackRequest === "function" &&
      !consumePlayerBackRequest[COMMON_RUNTIME_PATCHED]
    ) {
      const patched = function consumePlayerBackRequestWithStreamInfo(...args) {
        if (this.streamInfoVisible) {
          this.closeStreamInfo();
          return true;
        }
        if (
          this === universalBackButtonRequestScreen &&
          this.controlsVisible &&
          !this.hasBackDismissableOverlay?.() &&
          !this.isStartupErrorVisible?.() &&
          !this.isPostPlayVisible?.() &&
          !this.isPostPlayLoading?.() &&
          !this.episodeOptionsDialogVisible &&
          !this.isDialogOpen?.() &&
          typeof this.navigateBackToStreamScreen === "function"
        ) {
          return this.navigateBackToStreamScreen();
        }
        return consumePlayerBackRequest.apply(this, args);
      };
      patched[COMMON_RUNTIME_PATCHED] = true;
      PlayerScreen.consumeBackRequest = patched;
    }

    FocusEngine.requestBack = function requestBack({ universalButton = false } = {}) {
      const previousRequestScreen = universalBackButtonRequestScreen;
      universalBackButtonRequestScreen =
        universalButton && Router.getCurrent() === "player" ? Router.getCurrentScreen() : null;
      try {
        return this.handleBack(null, {
          repeat: false,
          preventDefault() {},
          stopPropagation() {},
          stopImmediatePropagation() {}
        });
      } finally {
        universalBackButtonRequestScreen = previousRequestScreen;
      }
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
        FocusEngine.requestBack({ universalButton: true });
      },
      true
    );

    Router.syncUniversalBackButton = function syncUniversalBackButton() {
      const backButton = globalThis.document?.getElementById?.("universalBackButton");
      if (backButton) {
        backButton.hidden = ["home", "search", "settings", "library"].includes(this.current);
      }
    };
    this.installRouterNavigationPatch(Router);
    for (const methodName of ["back"]) {
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
      (document.body || document.getElementById("app"))?.append(backButton);
    }
    backButton.hidden = true;

    const syncPlayerBackButton = (screen) => {
      const currentBackButton = globalThis.document?.getElementById?.("universalBackButton");
      if (currentBackButton && Router.getCurrent() === "player") {
        currentBackButton.hidden = !screen?.controlsVisible;
      }
    };

    const setControlsVisible = PlayerScreen.setControlsVisible;
    if (typeof setControlsVisible === "function" && !setControlsVisible[COMMON_RUNTIME_PATCHED]) {
      const patched = function setControlsVisibleWithBackButton(...args) {
        const result = setControlsVisible.apply(this, args);
        syncPlayerBackButton(this);
        return result;
      };
      patched[COMMON_RUNTIME_PATCHED] = true;
      PlayerScreen.setControlsVisible = patched;
    }

    const renderPlayerUi = PlayerScreen.renderPlayerUi;
    if (typeof renderPlayerUi === "function" && !renderPlayerUi[COMMON_RUNTIME_PATCHED]) {
      const patched = function (...args) {
        const result = renderPlayerUi.apply(this, args);
        this.uiRefs?.root?.removeAttribute?.("tabindex");
        Router.syncUniversalBackButton?.();
        syncPlayerBackButton(this);
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
