import { Link } from "react-router";

import { errorMessage } from "../../api/client";
import { useHome, useStartPlay } from "../../api/learn";
import { AccuracyBar, Loading } from "../../components/ui/Bits";
import { Button } from "../../components/ui/Button";
import { FormError } from "../../components/ui/Field";
import { percent } from "../../lib/format";
import { getIncludeHigher } from "../../lib/tier";
import { ReviewCard } from "../progress/ReviewCard";
import { ExamsCard } from "./ExamsCard";

export function HomePage() {
  const { data: home, isPending, error } = useHome();
  const start = useStartPlay();

  if (isPending) return <Loading />;
  if (!home) return <FormError message={errorMessage(error)} />;

  function quiz(topicId: number, subjectId: number | null) {
    start.mutate({ mode: "quiz", topic_id: topicId, subject_id: subjectId, include_higher: getIncludeHigher(subjectId) });
  }

  const weakest = home.weakest_topic;
  const firstTime = home.recent_topics.length === 0;
  // Don't list the weakest topic twice.
  const recent = home.recent_topics.filter((t) => t.topic_id !== weakest?.topic_id);

  return (
    <div className="space-y-5">
      <header className="flex items-center gap-4">
        <span
          className="grid size-14 shrink-0 place-items-center rounded-2xl bg-brand-600 text-2xl font-bold text-white"
          aria-hidden="true"
        >
          {home.user.username.slice(0, 1).toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-bold tracking-tight">Hey {home.user.username}</h1>
          <p className="text-sm text-muted">
            {home.user.graduated ? "Graduated" : `Year ${home.user.year_group}`} · 🔥 {home.user.streak_current}-day
            streak · {home.user.total_xp} XP
          </p>
        </div>
      </header>

      <ReviewCard due={home.due_reviews} />

      {firstTime ? (
        <section className="card space-y-3 p-4">
          <h2 className="font-bold">Start your first quiz</h2>
          <p className="text-sm text-muted">Pick a subject and topic. Quizzes are 10 quick questions.</p>
          <Link
            to="/revise"
            className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-brand-600 font-semibold text-white"
          >
            Choose a topic
          </Link>
        </section>
      ) : (
        <section className="space-y-3" aria-labelledby="quick-launch">
          <h2 id="quick-launch" className="text-sm font-semibold uppercase tracking-wide text-muted">
            Quick launch
          </h2>
          {weakest && (
            <div className="card space-y-2 border-rose-300 p-4 dark:border-rose-500/40">
              <p className="text-xs font-semibold uppercase tracking-wide text-rose-700 dark:text-rose-400">
                Your weakest topic
              </p>
              <div className="flex items-center justify-between gap-3">
                <p className="font-semibold">{weakest.name}</p>
                <span className="font-bold tabular-nums">{percent(weakest.accuracy)}</span>
              </div>
              <AccuracyBar accuracy={weakest.accuracy} />
              <Button block loading={start.isPending} onClick={() => quiz(weakest.topic_id, weakest.subject_id)}>
                Revise weakest topic
              </Button>
            </div>
          )}
          <ul className="grid gap-2">
            {recent.map((t) => (
              <li key={t.topic_id}>
                <button
                  type="button"
                  onClick={() => quiz(t.topic_id, t.subject_id)}
                  disabled={start.isPending}
                  className="card flex min-h-14 w-full items-center gap-3 px-4 text-left hover:border-brand-500"
                >
                  <span className="text-xl" aria-hidden="true">
                    ⚡
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold">{t.name}</span>
                    <span className="block truncate text-xs text-muted">
                      {t.subject_name} · {percent(t.accuracy)}
                    </span>
                  </span>
                  <span className="text-sm font-semibold text-brand-600 dark:text-brand-400">Play</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <FormError message={start.error ? errorMessage(start.error) : null} />

      <ExamsCard exams={home.exams} />
    </div>
  );
}
