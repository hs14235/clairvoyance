import { useSyncExternalStore } from "react";

const noSubscribe = () => () => {};

/**
 * Runs a browser feature check on the client only. Returns false during
 * server rendering so the first client render matches the static HTML.
 */
export function useBrowserSupport(check: () => boolean): boolean {
  return useSyncExternalStore(noSubscribe, check, () => false);
}
