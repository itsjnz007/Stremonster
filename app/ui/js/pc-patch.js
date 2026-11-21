const PC_RUNTIME_PATCHED = Symbol("pc-patch-runtime-patched");

function getHomeModernSidebars(root) {
  const sidebars = [];
  if (root?.matches?.("#home .home-screen-shell .modern-sidebar-shell")) {
    sidebars.push(root);
  }
  root?.querySelectorAll?.("#home .home-screen-shell .modern-sidebar-shell").forEach((sidebar) => {
    sidebars.push(sidebar);
  });
  return sidebars;
}

function syncHomeProfileRailButton(sidebar, Router) {
  const profile = sidebar.querySelector(".modern-sidebar-panel .modern-sidebar-profile");
  let trigger = sidebar.querySelector(":scope > .pc-sidebar-profile-trigger");
  if (!profile) {
    trigger?.remove();
    return;
  }

  const sourceMarkup = profile.outerHTML;
  if (!trigger || trigger.dataset.profileSourceMarkup !== sourceMarkup) {
    const replacement = profile.cloneNode(true);
    replacement.classList.remove("modern-sidebar-profile");
    replacement.classList.add("pc-sidebar-profile-trigger", "focusable");
    replacement.removeAttribute("data-nav-zone");
    replacement.removeAttribute("data-nav-index");
    replacement.setAttribute("type", "button");
    replacement.querySelector(".modern-sidebar-profile-name")?.remove();
    replacement.dataset.profileSourceMarkup = sourceMarkup;
    replacement.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      Router.navigate("profileSelection");
    });
    if (trigger) {
      trigger.replaceWith(replacement);
    } else {
      sidebar.append(replacement);
    }
    trigger = replacement;
  }

  const expanded = sidebar.classList.contains("expanded") || sidebar.classList.contains("opening");
  trigger.setAttribute("aria-hidden", expanded ? "true" : "false");
  trigger.tabIndex = expanded ? -1 : 0;
}

function isPlayerControlPointerTarget(target) {
  return Boolean(target?.closest?.("#playerUiRoot .player-control-btn, #playerUiRoot .player-progress-shell"));
}

export const PcPatch = {
  installRuntime({ FocusEngine, Router, Platform }) {
    if (this[PC_RUNTIME_PATCHED]) {
      return;
    }
    this[PC_RUNTIME_PATCHED] = true;

    Platform.isWebOS = () => true;

    const homeSidebarFocusableSelector = "#home .home-sidebar .focusable, #home .modern-sidebar-panel .focusable";
    let hasPendingSidebarPointerFocus = false;
    const trackSidebarPointerDown = (event) => {
      if (!event.target?.closest?.(homeSidebarFocusableSelector)) {
        return;
      }
      hasPendingSidebarPointerFocus = true;
      setTimeout(() => {
        hasPendingSidebarPointerFocus = false;
      }, 0);
    };
    document.addEventListener("pointerdown", trackSidebarPointerDown, true);
    document.addEventListener("mousedown", trackSidebarPointerDown, true);
    document.addEventListener(
      "focusin",
      (event) => {
        if (hasPendingSidebarPointerFocus && event.target?.closest?.(homeSidebarFocusableSelector)) {
          hasPendingSidebarPointerFocus = false;
          event.stopPropagation();
        }
      },
      true
    );
    document.addEventListener(
      "wheel",
      (event) => {
        const homeTarget = event.target?.closest?.("#home .home-main, #home .home-sidebar, #home .modern-sidebar-shell");
        const screen = Router.getCurrentScreen();
        if (!homeTarget || screen?.container?.id !== "home") {
          return;
        }

        screen.cancelModernCameraFollow?.({ stopAnimations: true });
        if (homeTarget.matches?.(".home-sidebar, .modern-sidebar-shell") || homeTarget.closest?.(".home-sidebar, .modern-sidebar-shell")) {
          const viewport = screen.getHomeViewport?.();
          if (!viewport || !Number(event.deltaY)) {
            return;
          }
          const deltaMultiplier = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? viewport.clientHeight : 1;
          event.preventDefault();
          viewport.scrollTop += Number(event.deltaY) * deltaMultiplier;
        }
      },
      { capture: true, passive: false }
    );

    const originalFocusPointerTarget = FocusEngine.focusPointerTarget;
    if (typeof originalFocusPointerTarget === "function" && !originalFocusPointerTarget[PC_RUNTIME_PATCHED]) {
      const patchedFocusPointerTarget = function (target, event) {
        const isPointerMove = event?.type === "mousemove" || event?.type === "pointermove";
        const isLibraryOrSettings = ["library", "settings"].includes(Router.getCurrent());
        if (
          target?.closest?.(homeSidebarFocusableSelector) ||
          (isPointerMove &&
            isLibraryOrSettings &&
            target?.closest?.(".home-sidebar .focusable, .modern-sidebar-panel .focusable, .modern-sidebar-pill"))
        ) {
          return false;
        }
        return originalFocusPointerTarget.call(this, target, event);
      };
      patchedFocusPointerTarget[PC_RUNTIME_PATCHED] = true;
      FocusEngine.focusPointerTarget = patchedFocusPointerTarget;
    }

    const originalProcessPointerMove = FocusEngine.processPointerMove;
    if (typeof originalProcessPointerMove === "function" && !originalProcessPointerMove[PC_RUNTIME_PATCHED]) {
      const patchedProcessPointerMove = function (event) {
        const previousTarget = this.lastPointerFocusTarget;
        const previousWasPlayerControl = isPlayerControlPointerTarget(previousTarget);
        const nextTarget = this.getPointerFocusable(event);
        const result = originalProcessPointerMove.call(this, event);

        if (previousWasPlayerControl && !isPlayerControlPointerTarget(nextTarget)) {
          previousTarget.classList?.remove("focused");
          if (document.activeElement === previousTarget) {
            previousTarget.blur?.();
          }
          if (this.lastPointerFocusTarget === previousTarget) {
            this.lastPointerFocusTarget = null;
          }
        }

        return result;
      };
      patchedProcessPointerMove[PC_RUNTIME_PATCHED] = true;
      FocusEngine.processPointerMove = patchedProcessPointerMove;
    }

    const syncProfileButtons = (root = document) => {
      getHomeModernSidebars(root).forEach((sidebar) => syncHomeProfileRailButton(sidebar, Router));
    };
    syncProfileButtons();
    if (typeof MutationObserver === "function" && document.body) {
      const observer = new MutationObserver((records) => {
        const affectedSidebars = new Set();
        records.forEach((record) => {
          const targetSidebar = record.target?.closest?.("#home .home-screen-shell .modern-sidebar-shell");
          if (targetSidebar) {
            affectedSidebars.add(targetSidebar);
          }
          record.addedNodes?.forEach((node) => {
            if (node?.nodeType === 1) {
              getHomeModernSidebars(node).forEach((sidebar) => affectedSidebars.add(sidebar));
            }
          });
          if (record.type === "attributes" && record.target?.matches?.("#home .home-screen-shell .modern-sidebar-shell")) {
            affectedSidebars.add(record.target);
          }
        });
        affectedSidebars.forEach((sidebar) => syncHomeProfileRailButton(sidebar, Router));
      });
      observer.observe(document.body, {
        attributes: true,
        attributeFilter: ["class"],
        childList: true,
        subtree: true
      });
    }
  }
};
