import type { ReactNode } from "react";

export function AuthLayout({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="min-h-dvh px-4 pb-10 pt-[calc(2.5rem+env(safe-area-inset-top))]">
      <div className="mx-auto max-w-md space-y-6">
        <div className="flex items-center gap-2">
          <span className="grid size-10 place-items-center rounded-xl bg-brand-600 text-xl text-zap" aria-hidden="true">
            ⚡
          </span>
          <span className="text-xl font-bold tracking-tight">Revision Battle</span>
        </div>
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
          {subtitle && <p className="text-muted">{subtitle}</p>}
        </div>
        <div className="card p-5">{children}</div>
      </div>
    </div>
  );
}
