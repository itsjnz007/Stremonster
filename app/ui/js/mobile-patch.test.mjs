import assert from "node:assert/strict";
import test from "node:test";
import { MobilePatch } from "./mobile-patch.js";

test("standalone touch devices use mobile sizing when the pointer query misses", (t) => {
  const globalNames = ["document", "navigator", "matchMedia", "getComputedStyle", "addEventListener"];
  const previousDescriptors = new Map(
    globalNames.map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)])
  );
  t.after(() => {
    for (const [name, descriptor] of previousDescriptors) {
      if (descriptor) {
        Object.defineProperty(globalThis, name, descriptor);
      } else {
        delete globalThis[name];
      }
    }
  });

  const classes = new Map();
  const styles = new Map();
  const root = {
    classList: {
      toggle(name, enabled) {
        classes.set(name, enabled);
      }
    },
    style: {
      setProperty(name, value) {
        styles.set(name, value);
      },
      removeProperty(name) {
        styles.delete(name);
      }
    }
  };

  Object.defineProperties(globalThis, {
    document: { configurable: true, value: { documentElement: root } },
    navigator: { configurable: true, value: { maxTouchPoints: 5, standalone: false } },
    matchMedia: {
      configurable: true,
      value(query) {
        return {
          matches: query === "(display-mode: standalone)" || query === "(orientation: portrait)",
          addEventListener() {}
        };
      }
    },
    getComputedStyle: {
      configurable: true,
      value() {
        return { getPropertyValue: () => "0.5" };
      }
    },
    addEventListener: { configurable: true, value() {} }
  });

  MobilePatch.installRuntime();

  assert.equal(classes.get("mobile-device"), true);
  assert.equal(styles.get("--mobile-ui-compensation"), "200%");
});
