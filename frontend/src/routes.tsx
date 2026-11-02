import type { RouteObject } from "react-router";

import { AppShell } from "./components/AppShell";
import { NotFound } from "./components/NotFound";
import { LoginPage } from "./features/auth/LoginPage";
import { SignupPage } from "./features/auth/SignupPage";
import { CreatePage } from "./features/create/CreatePage";
import { HomePage } from "./features/home/HomePage";
import { MePage } from "./features/me/MePage";
import { RanksPage } from "./features/ranks/RanksPage";
import { RevisePage } from "./features/revise/RevisePage";

export const routes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
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
];
