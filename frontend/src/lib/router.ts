import { useMemo, useSyncExternalStore } from "react";
import { parseHash, withParams } from "./hash";
import type { Route } from "./hash";

function subscribe(onChange: () => void): () => void {
  window.addEventListener("hashchange", onChange);
  return () => window.removeEventListener("hashchange", onChange);
}

/** The current route, kept in sync with the address bar. */
export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash, () => "");
  return useMemo(() => parseHash(hash), [hash]);
}

/** Change query parameters of the current route (null removes one). Replaces the history entry by default. */
export function setParams(updates: Record<string, string | null>, replace = true): void {
  const next = withParams(window.location.hash, updates);
  if (replace) {
    window.history.replaceState(null, "", next);
    window.dispatchEvent(new HashChangeEvent("hashchange"));   // replaceState does not fire it by itself
  } else {
    window.location.hash = next;
  }
}