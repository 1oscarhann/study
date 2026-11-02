import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import type { Me } from "../api/types";

export const ME: Me = {
  username: "SwiftOtter42",
  year_group: 10,
  graduated: false,
  can_change_year_group: true,
  is_admin: false,
  total_xp: 0,
  league_tier: 0,
  streak_current: 0,
  created_at: "2026-11-02T12:00:00Z",
};

export function apiError(status: number, detail: string, field: string | null = null, code = "error") {
  return HttpResponse.json({ detail, code, field }, { status });
}

/** Default: logged out, server healthy. Tests add handlers with server.use(...). */
export const server = setupServer(
  http.get("*/api/me", () => apiError(401, "Please log in.", null, "not_authenticated")),
  http.get("*/api/health", () => HttpResponse.json({ status: "ok", db: "ok" })),
);

export function loggedInAs(me: Partial<Me> = {}) {
  server.use(http.get("*/api/me", () => HttpResponse.json({ ...ME, ...me })));
}
