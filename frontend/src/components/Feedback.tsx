import type { ReactNode } from "react";
import type { ApiError } from "../api/client";

export function Skeleton({ height = 120, label = "Loading" }: { height?: number; label?: string }) {
  return <div className="skeleton" style={{ height }} role="status" aria-label={label} />;
}

export function ErrorState({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  return (
    <div className="state state--error" role="alert">
      <p className="state-title">{error.kind === "network" ? "Can\u2019t reach the server" : "Something went wrong"}</p>
      <p>{error.message}</p>
      {error.requestId ? <p className="muted small">Reference: {error.requestId}</p> : null}
      <button type="button" className="btn" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state">
      <p className="state-title">{title}</p>
      {children}
    </div>
  );
}