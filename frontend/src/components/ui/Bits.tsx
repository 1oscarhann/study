import type { ReactNode } from "react";
import { Link } from "react-router";

export function PageTitle({ children, back }: { children: ReactNode; back?: { to: string; label: string } }) {
  return (
    <div className="space-y-1">
      {back && (
        <Link to={back.to} className="text-sm font-semibold text-brand-600 dark:text-brand-400">
          ← {back.label}
        </Link>
      )}
      <h1 className="text-2xl font-bold tracking-tight">{children}</h1>
    </div>
  );
}

export function AccuracyBar({ accuracy }: { accuracy: number | null | undefined }) {
  const pct = accuracy == null ? 0 : Math.round(accuracy * 100);
  const colour = pct >= 80 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--line)]" aria-hidden="true">
      <div className={`h-full rounded-full ${colour}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Loading() {
  return (
    <p role="status" className="py-8 text-center text-muted">
      Loading…
    </p>
  );
}
