import type { ComponentType, SVGProps } from "react";
import { NavLink } from "react-router";

import { CreateIcon, HomeIcon, MeIcon, RanksIcon, ReviseIcon } from "./icons";

interface Tab {
  to: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
}

export const TABS: Tab[] = [
  { to: "/", label: "Home", icon: HomeIcon },
  { to: "/revise", label: "Revise", icon: ReviseIcon },
  { to: "/create", label: "Create", icon: CreateIcon },
  { to: "/ranks", label: "Ranks", icon: RanksIcon },
  { to: "/me", label: "Me", icon: MeIcon },
];

export function BottomNav() {
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-10 border-t border-[var(--line)] bg-[var(--card)]/95 backdrop-blur pb-[env(safe-area-inset-bottom)]"
    >
      <ul className="mx-auto grid max-w-lg grid-cols-5">
        {TABS.map(({ to, label, icon: TabIcon }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `flex min-h-14 flex-col items-center justify-center gap-0.5 text-xs font-medium transition-colors ${
                  isActive ? "text-brand-600 dark:text-brand-400" : "text-muted hover:text-[var(--ink)]"
                }`
              }
            >
              <TabIcon className="size-6" />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
