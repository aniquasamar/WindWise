import { useEffect, useRef, useState } from "react";
import { useApi } from "./api/hooks";
import type { MetaOut } from "./api/types";
import { AssumptionsPanel } from "./components/AssumptionsPanel";
import { Logo } from "./components/Logo";
import { ThemeToggle } from "./components/ThemeToggle";
import { buildHash } from "./lib/hash";
import { useRoute } from "./lib/router";
import { useTheme } from "./lib/useTheme";
import { AccuracyPage } from "./pages/AccuracyPage";
import { ForecastPage } from "./pages/ForecastPage";

const PAGES = [
  { path: "/forecast", label: "Forecast", title: "Forecast" },
  { path: "/accuracy", label: "Accuracy", title: "Accuracy" },
];

export default function App() {
  const route = useRoute();
  const [theme, toggleTheme] = useTheme();
  const meta = useApi<MetaOut>("/api/v1/meta");
  const [showAssumptions, setShowAssumptions] = useState(false);
  const mainRef = useRef<HTMLElement | null>(null);

  const onAccuracy = route.path === "/accuracy";
  const current = onAccuracy ? PAGES[1] : PAGES[0];
  const cutoff = route.params.get("cutoff") ?? meta.data?.defaults.cutoff ?? "09:00";
  // Carry the chosen cutoff and confidence from page to page.
  const carry = { cutoff: route.params.get("cutoff"), confidence: route.params.get("confidence") };

  useEffect(() => {
    document.title = `${current.title} \u2013 WindWise`;
  }, [current.title]);

  return (
    <>
      <button type="button" className="skip-link" onClick={() => mainRef.current?.focus()}>
        Skip to content
      </button>
      <header className="site-header">
        <div className="header-inner">
          <a className="brand" href={buildHash("/forecast", carry)} aria-label="WindWise home">
            <Logo />
            <span>
              <span className="brand-name">WindWise</span>
              <span className="brand-tag">Day-ahead wind forecast reliability</span>
            </span>
          </a>
          <nav className="nav" aria-label="Pages">
            {PAGES.map((p) => (
              <a key={p.path} href={buildHash(p.path, carry)} aria-current={route.path === p.path || (p.path === "/forecast" && !onAccuracy) ? "page" : undefined}>
                {p.label}
              </a>
            ))}
          </nav>
          <div className="header-tools">
            <button
              type="button"
              className="chip"
              aria-expanded={showAssumptions}
              aria-controls="assumptions-panel"
              onClick={() => setShowAssumptions((v) => !v)}
            >
              <span>Cutoff {cutoff} UK · Elexon data · Decisions 1–31 Jan 2026</span>
              <svg className="caret" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </div>
        </div>
      </header>
      {showAssumptions ? <AssumptionsPanel meta={meta.data} id="assumptions-panel" /> : null}

      <main ref={mainRef} tabIndex={-1}>
        {onAccuracy ? <AccuracyPage meta={meta.data} /> : <ForecastPage meta={meta.data} />}
      </main>

      <footer className="site-footer">
        <p>Data: Elexon Insights Solution (BMRS) national wind actuals (FUELHH) and forecasts (WINDFOR), January 2026 decisions.</p>
        <p>See the README for details.</p>
      </footer>
    </>
  );
}