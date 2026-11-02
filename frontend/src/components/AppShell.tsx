import { Outlet } from "react-router";

import { BottomNav } from "./BottomNav";

export function AppShell() {
  return (
    <div className="min-h-dvh pb-[calc(4rem+env(safe-area-inset-bottom))]">
      <header className="sticky top-0 z-10 border-b border-[var(--line)] bg-[var(--surface)]/90 backdrop-blur pt-[env(safe-area-inset-top)]">
        <div className="mx-auto flex h-14 max-w-lg items-center gap-2 px-4">
          <span className="grid size-8 place-items-center rounded-lg bg-brand-600 text-zap" aria-hidden="true">
            ⚡
          </span>
          <span className="text-lg font-bold tracking-tight">Revision Battle</span>
        </div>
      </header>
      <main className="mx-auto max-w-lg px-4 py-5">
        <Outlet />
      </main>
      <BottomNav />
    </div>
  );
}
