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
import { PlayPage } from "./features/play/PlayPage";
import { WeakSpotsPage } from "./features/progress/WeakSpotsPage";
import { RanksPage } from "./features/ranks/RanksPage";
import { RevisePage } from "./features/revise/RevisePage";
import { SubjectPage } from "./features/revise/SubjectPage";
import { TopicPage } from "./features/revise/TopicPage";

export const routes: RouteObject[] = [
  { element: <GuestOnly />, children: [{ path: "/login", element: <LoginPage /> }] },
  // Signup/recover handle the logged-in redirect themselves (see useGuestRedirect).
  { path: "/signup", element: <SignupPage /> },
  { path: "/recover", element: <RecoverPage /> },
  {
    element: <RequireAuth />,
    children: [
      // Full-screen, no bottom nav: nothing to tap by accident mid-question.
      { path: "/play/:sessionId", element: <PlayPage /> },
      {
        path: "/",
        element: <AppShell />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "revise", element: <RevisePage /> },
          { path: "revise/:subjectId", element: <SubjectPage /> },
          { path: "revise/:subjectId/:topicId", element: <TopicPage /> },
          { path: "weak-spots", element: <WeakSpotsPage /> },
          { path: "create", element: <CreatePage /> },
          { path: "ranks", element: <RanksPage /> },
          { path: "me", element: <MePage /> },
          { path: "*", element: <NotFound /> },
        ],
      },
    ],
  },
];
