import { useEffect, useState } from "react";
import { Navigate, Outlet, useLocation, useSearchParams } from "react-router";

import { useMe } from "../api/auth";
import { safeNext } from "../features/auth/safeNext";
import { Button } from "./ui/Button";

export function Splash() {
  // Render's free tier can take up to a minute to wake; say so if it's slow.
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 3000);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="grid min-h-dvh place-items-center px-6 text-center" role="status">
      <div className="space-y-3">
        <span className="mx-auto grid size-14 animate-pulse place-items-center rounded-2xl bg-brand-600 text-2xl text-zap">
          ⚡
        </span>
        <p className="text-muted">{slow ? "Waking up the server… this can take up to a minute." : "Loading…"}</p>
      </div>
    </div>
  );
}

export function ServerDown({ retry }: { retry: () => void }) {
  return (
    <div className="grid min-h-dvh place-items-center px-6 text-center">
      <div className="max-w-sm space-y-4">
        <h1 className="text-2xl font-bold tracking-tight">Can't reach the server</h1>
        <p className="text-muted">Check your connection, or give it a minute if the server is waking up.</p>
        <Button onClick={retry}>Try again</Button>
      </div>
    </div>
  );
}

/** Logged-in pages. Logged-out visitors go to /login and come back afterwards. */
export function RequireAuth() {
  const { data: me, isPending, isError, refetch } = useMe();
  const location = useLocation();
  if (isPending) return <Splash />;
  if (isError) return <ServerDown retry={() => void refetch()} />;
  if (!me) {
    const next = location.pathname + location.search;
    return <Navigate to={next === "/" ? "/login" : `/login?next=${encodeURIComponent(next)}`} replace />;
  }
  return <Outlet />;
}

/** Login/signup/recover: if you're already logged in, skip them. */
export function GuestOnly() {
  const { data: me, isPending, isError, refetch } = useMe();
  const [params] = useSearchParams();
  if (isPending) return <Splash />;
  if (isError) return <ServerDown retry={() => void refetch()} />;
  if (me) return <Navigate to={safeNext(params.get("next"))} replace />;
  return <Outlet />;
}

/**
 * For signup/recover: skip the page if already logged in, but never while a freshly
 * issued recovery code is on screen (a background refetch mustn't navigate away).
 */
export function useGuestRedirect(showingRecoveryCode: boolean) {
  const { data: me, isPending } = useMe();
  if (showingRecoveryCode) return null;
  if (isPending) return <Splash />;
  if (me) return <Navigate to="/" replace />;
  return null;
}
