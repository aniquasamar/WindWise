// Theme choice: an explicit saved choice wins; otherwise follow the operating system.

export type Theme = "light" | "dark";
export const THEME_KEY = "windwise-theme";

export function resolveTheme(stored: string | null, prefersDark: boolean): Theme {
  if (stored === "light" || stored === "dark") return stored;
  return prefersDark ? "dark" : "light";
}

export function readStoredTheme(storage: Pick<Storage, "getItem"> | undefined): string | null {
  try {
    return storage ? storage.getItem(THEME_KEY) : null;
  } catch {
    return null; // storage can be blocked (private mode)
  }
}

export function saveTheme(storage: Pick<Storage, "setItem"> | undefined, theme: Theme): void {
  try {
    storage?.setItem(THEME_KEY, theme);
  } catch {
    // ignore: the choice just will not persist
  }
}