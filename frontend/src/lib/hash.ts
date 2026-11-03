// Pure helpers for hash-based routes such as "#/forecast?date=2026-01-28&cutoff=09:00".
// Hash routing needs no server configuration, so deep links work on any static host.

export interface Route {
  path: string;
  params: URLSearchParams;
}

export const DEFAULT_PATH = "/forecast";

export function parseHash(hash: string): Route {
  const raw = hash.startsWith("#") ? hash.slice(1) : hash;
  const cut = raw.indexOf("?");
  const pathPart = cut === -1 ? raw : raw.slice(0, cut);
  const query = cut === -1 ? "" : raw.slice(cut + 1);
  const path = pathPart === "" || pathPart === "/" ? DEFAULT_PATH : pathPart.startsWith("/") ? pathPart : `/${pathPart}`;
  return { path, params: new URLSearchParams(query) };
}

export function buildHash(path: string, params: Record<string, string | null | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") search.set(key, value);
  }
  const query = search.toString().replace(/%3A/g, ":");
  return `#${path}${query ? `?${query}` : ""}`;
}

/** Return a new hash with some params changed (null removes a param). */
export function withParams(hash: string, updates: Record<string, string | null>): string {
  const route = parseHash(hash);
  const merged: Record<string, string | null | undefined> = Object.fromEntries(route.params.entries());
  for (const [key, value] of Object.entries(updates)) merged[key] = value;
  return buildHash(route.path, merged);
}