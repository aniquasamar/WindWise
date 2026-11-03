import { useCallback, useEffect, useState } from "react";
import { readStoredTheme, resolveTheme, saveTheme } from "./theme";
import type { Theme } from "./theme";

function storage(): Storage | undefined {
  try {
    return window.localStorage;
  } catch {
    return undefined; // access itself can throw when storage is blocked
  }
}

function prefersDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => resolveTheme(readStoredTheme(storage()), prefersDark()));

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  // Follow the operating system while the user has not chosen explicitly.
  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (readStoredTheme(storage()) === null) setTheme(query.matches ? "dark" : "light");
    };
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  const toggle = useCallback(() => {
    setTheme((previous) => {
      const next: Theme = previous === "dark" ? "light" : "dark";
      saveTheme(storage(), next);
      return next;
    });
  }, []);

  return [theme, toggle];
}