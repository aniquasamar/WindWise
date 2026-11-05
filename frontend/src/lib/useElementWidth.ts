import { useEffect, useState } from "react";

/** Width of an element, kept up to date as it resizes. The first measurement arrives with the observer. */
export function useElementWidth(ref: { current: HTMLDivElement | null }, fallback = 720): number {
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(Math.max(280, Math.floor(el.clientWidth))));
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}