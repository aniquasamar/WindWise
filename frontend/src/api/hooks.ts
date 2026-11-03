import { useCallback, useEffect, useState } from "react";
import { ApiError, getJson } from "./client";

interface Entry {
  data?: unknown;
  error?: ApiError;
}

interface Result<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

// Responses never change within a deployment, so a simple in-memory cache is enough.
const cache = new Map<string, unknown>();

function toApiError(err: unknown): ApiError {
  return err instanceof ApiError ? err : new ApiError("network", "Something went wrong while loading data.", null, "unknown", null);
}

/**
 * Load JSON from `url` (pass null to wait).
 *
 * What is shown is worked out while rendering from the results received so far, so effects never
 * set state synchronously. While a new request is in flight the previous data stays on screen,
 * so the page does not flash empty when a control changes.
 */
export function useApi<T>(url: string | null): Result<T> {
  const [results, setResults] = useState<Record<string, Entry>>({});
  const [lastData, setLastData] = useState<T | null>(null);
  const [attempt, setAttempt] = useState(0);

  const cached = url !== null && cache.has(url);
  const settled = url === null ? undefined : (results[url] ?? (cached ? { data: cache.get(url) } : undefined));

  useEffect(() => {
    if (url === null || settled !== undefined) return;
    const controller = new AbortController();
    getJson<T>(url, controller.signal)
      .then((data) => {
        cache.set(url, data);
        setResults((previous) => ({ ...previous, [url]: { data } }));
        setLastData(data);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setResults((previous) => ({ ...previous, [url]: { error: toApiError(err) } }));
      });
    return () => controller.abort();
    // `attempt` is a deliberate trigger: reload() clears the stored result and bumps it.
  }, [url, settled, attempt]);

  const reload = useCallback(() => {
    if (url === null) return;
    cache.delete(url);
    setResults((previous) => {
      const next = { ...previous };
      delete next[url];
      return next;
    });
    setAttempt((n) => n + 1);
  }, [url]);

  const error = settled?.error ?? null;
  const data = settled && "data" in settled ? (settled.data as T) : error ? null : lastData;
  return { data, error, loading: url !== null && settled === undefined, reload };
}