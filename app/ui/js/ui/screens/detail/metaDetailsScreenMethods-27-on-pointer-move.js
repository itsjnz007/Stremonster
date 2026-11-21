/* eslint-disable no-unused-vars */
import * as internals from "./metaDetailsScreenContext.js";

export function createMetaDetailsScreenMethods27() {
  const { ScreenUtils, buildYoutubeEmbedUrl, Router, HERO_HOLD_DELAY_MS, EPISODE_HOLD_DELAY_MS, POSTER_HOLD_DELAY_MS } = internals;

  return {
    getDetailPointerHoldTarget(target) {
      const node = target?.closest?.(".focusable");
      if (!node || !this.container?.contains?.(node)) {
        return null;
      }
      if (this.isHeroHoldTarget(node)) {
        return { node, kind: "hero", delay: HERO_HOLD_DELAY_MS };
      }
      if (this.isEpisodeHoldTarget(node) || this.isSeasonHoldTarget(node)) {
        return {
          node,
          kind: this.isEpisodeHoldTarget(node) ? "episode" : "season",
          delay: EPISODE_HOLD_DELAY_MS
        };
      }
      if (this.isPosterHoldTarget(node)) {
        return { node, kind: "poster", delay: POSTER_HOLD_DELAY_MS };
      }
      return null;
    },
    openDetailPointerHoldMenu(hold) {
      if (hold.kind === "hero") {
        if (hold.node.dataset.action === "playDefault") {
          return this.openHeroPlayMenu();
        }
        void this.openLibraryListMenu();
        return true;
      }
      if (hold.kind === "episode") {
        return this.openEpisodeHoldMenu(hold.node);
      }
      if (hold.kind === "season") {
        return this.openSeasonHoldMenu(hold.node);
      }
      if (hold.kind === "poster") {
        void this.openPosterOptionsMenu(hold.node);
        return true;
      }
      return false;
    },
    cancelDetailPointerHold() {
      if (this.detailPointerHoldTimer) {
        clearTimeout(this.detailPointerHoldTimer);
        this.detailPointerHoldTimer = null;
      }
      this.detailPointerHold = null;
    },
    clearDetailPointerClickSuppression() {
      if (this.detailPointerClickSuppressTimer) {
        clearTimeout(this.detailPointerClickSuppressTimer);
        this.detailPointerClickSuppressTimer = null;
      }
      this.detailPointerClickSuppressTarget = null;
    },
    suppressDetailPointerClick(node) {
      this.clearDetailPointerClickSuppression();
      this.detailPointerClickSuppressTarget = node;
      this.detailPointerClickSuppressTimer = setTimeout(() => {
        this.detailPointerClickSuppressTimer = null;
        this.detailPointerClickSuppressTarget = null;
      }, 1000);
    },
    consumeDetailPointerClick(target) {
      const node = target?.closest?.(".focusable") || target;
      if (!this.detailPointerClickSuppressTarget || node !== this.detailPointerClickSuppressTarget) {
        return false;
      }
      this.clearDetailPointerClickSuppression();
      return true;
    },
    onDetailPointerDown(event) {
      if (event.button !== 0 || event.isPrimary === false) {
        return;
      }
      const hold = this.getDetailPointerHoldTarget(event.target);
      if (!hold) {
        return;
      }
      this.cancelDetailPointerHold();
      const pending = {
        ...hold,
        pointerId: event.pointerId,
        pointerType: event.pointerType,
        startX: Number(event.clientX),
        startY: Number(event.clientY),
        triggered: false
      };
      this.detailPointerHold = pending;
      this.detailPointerHoldTimer = setTimeout(() => {
        if (
          this.detailPointerHold !== pending ||
          !pending.node.isConnected ||
          !this.container?.contains?.(pending.node) ||
          Router.getCurrent() !== "detail"
        ) {
          return;
        }
        this.detailPointerHoldTimer = null;
        pending.triggered = true;
      }, pending.delay);
    },
    onDetailPointerMove(event) {
      const pending = this.detailPointerHold;
      if (!pending || pending.triggered || event.pointerId !== pending.pointerId) {
        return;
      }
      const deltaX = Number(event.clientX) - pending.startX;
      const deltaY = Number(event.clientY) - pending.startY;
      if (Math.hypot(deltaX, deltaY) > 12) {
        this.cancelDetailPointerHold();
      }
    },
    onDetailPointerUp(event) {
      const pending = this.detailPointerHold;
      if (!pending || event.pointerId !== pending.pointerId) {
        return;
      }
      this.cancelDetailPointerHold();
      if (!pending.triggered) {
        return;
      }
      event.preventDefault?.();
      this.suppressDetailPointerClick(pending.node);
      this.openDetailPointerHoldMenu(pending);
    },
    onDetailPointerCancel(event) {
      const pending = this.detailPointerHold;
      if (!pending || event.pointerId !== pending.pointerId) {
        return;
      }
      this.cancelDetailPointerHold();
      if (pending.triggered) {
        this.suppressDetailPointerClick(pending.node);
        this.openDetailPointerHoldMenu(pending);
      }
    },
    onDetailContextMenu(event) {
      const hold = this.getDetailPointerHoldTarget(event.target);
      if (!hold) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      if (this.detailPointerClickSuppressTarget === hold.node) {
        return;
      }
      const pending = this.detailPointerHold;
      if (pending?.node === hold.node && pending.triggered) {
        this.cancelDetailPointerHold();
        if (pending.pointerType === "touch" || event.pointerType === "touch") {
          this.suppressDetailPointerClick(hold.node);
        }
        this.openDetailPointerHoldMenu(hold);
        return;
      }
      const isTouch = event.pointerType === "touch" || this.detailPointerHold?.pointerType === "touch";
      this.cancelDetailPointerHold();
      if (isTouch) {
        this.suppressDetailPointerClick(hold.node);
      }
      this.openDetailPointerHoldMenu(hold);
    },
    onDetailPointerClick(event) {
      if (!this.consumeDetailPointerClick(event.target)) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
    },
    removeDetailPointerHandlers() {
      const handlers = this.detailPointerHandlers;
      if (!handlers) {
        return;
      }
      this.container?.removeEventListener("pointerdown", handlers.down, true);
      this.container?.removeEventListener("contextmenu", handlers.contextmenu, true);
      this.container?.removeEventListener("click", handlers.click, true);
      document.removeEventListener("pointermove", handlers.move, true);
      document.removeEventListener("pointerup", handlers.up, true);
      document.removeEventListener("pointercancel", handlers.cancel, true);
      this.detailPointerHandlers = null;
      this.cancelDetailPointerHold();
      this.clearDetailPointerClickSuppression();
    },
    onPointerMove() {
      if (this.isTrailerPlaying && this.trailerPlaybackMode === "manual") {
        this.restartTrailerControlsTimer();
      }
    },
    onPointerFocus() {},
    onPointerActivate(target) {
      if (this.consumeDetailPointerClick(target)) {
        return true;
      }
      if (!target || !this.container?.contains?.(target)) {
        return false;
      }
      const actionTarget = target?.closest?.("[data-action]");
      const action = String(actionTarget?.dataset?.action || "");
      if (action === "toggleTrailer") {
        this.playTrailer({ muted: false, restart: true, initiatedByUser: true });
        return true;
      }
      if (action === "openSharedTrailer") {
        const ytId = String(actionTarget.dataset.trailerYtId || "").trim();
        if (!ytId) {
          return false;
        }
        this.trailerSource = {
          kind: "youtube",
          ytId,
          embedUrl: buildYoutubeEmbedUrl(ytId, { muted: false })
        };
        this.playTrailer({
          muted: false,
          restart: true,
          initiatedByUser: true,
          preserveSource: true
        });
        return true;
      }
      if (action === "openTmdbEntity") {
        return this.openTmdbEntityFromNode(actionTarget);
      }
      if (!action) {
        return false;
      }

      // Pointer activation is a click, not a key-down/key-up hold. Reuse the
      // Android-aligned OK dispatcher so every detail action stays in one path.
      const activation = this.onKeyDown({
        keyCode: 13,
        pointerActivation: true,
        target: actionTarget,
        preventDefault() {},
        stopPropagation() {},
        stopImmediatePropagation() {}
      });
      activation?.catch?.((error) => console.warn("Detail pointer activation failed", error));
      return true;
    },
    async onKeyUp(event) {
      if (Number(event?.keyCode || 0) !== 13) {
        return;
      }
      const current = this.container?.querySelector(".series-episode-card.focusable.focused") || null;
      if (await this.completePendingEpisodeHold(current, event)) {
        event?.preventDefault?.();
        return;
      }
      const season = this.container?.querySelector(".series-season-btn.focusable.focused") || null;
      if (this.completePendingSeasonHold(season, event)) {
        event?.preventDefault?.();
        return;
      }
      const poster = this.container?.querySelector(".detail-morelike-card.focusable.focused") || null;
      if (this.completePendingPosterHold(poster, event)) {
        event?.preventDefault?.();
        return;
      }
      const hero = this.container?.querySelector(".series-detail-actions .focusable.focused") || null;
      if (await this.completePendingHeroHold(hero, event)) {
        event?.preventDefault?.();
      }
    },
    cleanup() {
      this.synopsisDialog?.destroy();
      this.synopsisDialog = null;
      this.shuffleDialog?.destroy();
      this.shuffleDialog = null;
      this.commentOverlayDialog?.destroy();
      this.commentOverlayDialog = null;
      this.commentOverlay = null;
      this.detailLoadToken = (this.detailLoadToken || 0) + 1;
      this.cancelTraktCommentsRequest();
      if (this.seasonSwitchTimer) {
        clearTimeout(this.seasonSwitchTimer);
        this.seasonSwitchTimer = null;
      }
      this.cancelPendingEpisodeHold();
      this.cancelPendingSeasonHold();
      this.cancelPendingPosterHold();
      this.cancelPendingHeroHold();
      this.removeDetailPointerHandlers();
      this.posterOptionsController?.destroy?.({ restoreFocus: false });
      this.posterOptionsController = null;
      this.posterOptionsFocusRestore = null;
      this.destroyDetailHoldDialog();
      this.episodeHoldMenu = null;
      this.seasonHoldMenu = null;
      this.heroPlayMenu = null;
      this.libraryListMenu = null;
      if (this.episodeVirtualSyncRaf) {
        cancelAnimationFrame(this.episodeVirtualSyncRaf);
        this.episodeVirtualSyncRaf = null;
      }
      this.episodeThumbnailPrefetchCache = new Set();
      if (this.episodeThumbObserver) {
        try {
          this.episodeThumbObserver.disconnect();
        } catch (_) {}
        this.episodeThumbObserver = null;
      }
      this.clearEpisodeTitleMarquee(this.episodeMarqueeTitle);
      this.selectedSeasonEpisodeState = null;
      if (this.episodeTrackScrollNode && this.episodeTrackScrollHandler) {
        this.episodeTrackScrollNode.removeEventListener("scroll", this.episodeTrackScrollHandler);
      }
      this.episodeTrackScrollNode = null;
      this.episodeTrackScrollHandler = null;
      this.episodeVirtualWindow = null;
      this.episodeVirtualMetrics = null;
      this.stopTrailerPlayback({
        keepDom: false,
        restartAutoplay: false,
        restoreFocus: false,
        immediateClear: true
      });
      if (this.detailScrollHandler && this.container) {
        const content = this.container.querySelector(".series-detail-content");
        if (content) {
          content.removeEventListener("scroll", this.detailScrollHandler);
        }
        this.detailScrollHandler = null;
      }
      if (this.detailFocusHandler && this.container) {
        this.container.removeEventListener("focusin", this.detailFocusHandler, true);
        this.detailFocusHandler = null;
      }
      if (this.detailClickHandler && this.container) {
        this.container.removeEventListener("click", this.detailClickHandler, true);
        this.detailClickHandler = null;
      }
      if (this.trailerProxyMessageHandler) {
        window.removeEventListener("message", this.trailerProxyMessageHandler);
        this.trailerProxyMessageHandler = null;
      }
      ScreenUtils.hide(this.container);
    }
  };
}
