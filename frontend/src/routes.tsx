import type { RouteObject } from "react-router";

import { AppShell } from "./components/AppShell";
import { GuestOnly, RequireAuth } from "./components/guards";
import { NotFound } from "./components/NotFound";
import { LoginPage } from "./features/auth/LoginPage";
import { RecoverPage } from "./features/auth/RecoverPage";
import { SignupPage } from "./features/auth/SignupPage";
import { CreatePage } from "./features/create/CreatePage";
import { HomePage } from "./features/home/HomePage";
import { MePage } from "./features/me/MePage";
import { RanksPage } from "./features/ranks/RanksPage";
import { RevisePage } from "./features/revise/RevisePage";

export const routes: RouteObject[] = [
  { element: <GuestOnly />, children: [{ path: "/login", element: <LoginPage /> }] },
  // Signup/recover handle the logged-in redirect themselves (see useGuestRedirect).
  { path: "/signup", element: <SignupPage /> },
  { path: "/recover", element: <RecoverPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        path: "/",
        element: <AppShell />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "revise", element: <RevisePage /> },
          { path: "create", element: <CreatePage /> },
          { path: "ranks", element: <RanksPage /> },
          { path: "me", element: <MePage /> },
          { path: "*", element: <NotFound /> },
        ],
      },
    ],
  },
];
