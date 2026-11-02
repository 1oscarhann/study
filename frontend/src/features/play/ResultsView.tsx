import { Link } from "react-router";

import { useStartPlay } from "../../api/learn";
import type { Summary } from "../../api/types";
import { errorMessage } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { FormError } from "../../components/ui/Field";
import { percent } from "../../lib/format";
import { getIncludeHigher } from "../../lib/tier";

function headline(summary: Summary): string {
  const acc = summary.accuracy ?? 0;
  if (summary.answered === 0) return "Quiz ended";
  if (acc === 1) return "Perfect score! 🎉";
  if (acc >= 0.8) return "Great work!";
  if (acc >= 0.5) return "Nice going";
  return "Good practice";
}

export function ResultsView({ summary }: { summary: Summary }) {
  const start = useStartPlay();
  const isReview = summary.mode === "review";
  const topicHref =
    summary.topic && summary.subject_id ? `/revise/${summary.subject_id}/${summary.topic.id}` : "/revise";

  function playAgain() {
    if (isReview) start.mutate({ mode: "review" });
    else if (summary.topic)
      start.mutate({
        mode: "quiz",
        topic_id: summary.topic.id,
        subject_id: summary.subject_id,
        include_higher: getIncludeHigher(summary.subject_id),
      });
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2 text-center">
        <p className="text-sm font-semibold uppercase tracking-wide text-muted">
          {isReview ? "Review" : summary.topic?.name}
        </p>
        <h1 className="text-3xl font-bold tracking-tight">{headline(summary)}</h1>
        <p className="text-6xl font-black tracking-tight text-brand-600 dark:text-brand-400">
          {summary.correct}
          <span className="text-3xl text-muted">/{summary.answered}</span>
        </p>
        <p className="text-muted">{percent(summary.accuracy)} correct</p>
      </div>

      {summary.answered > 0 && (
        <ol className="card divide-y divide-[var(--line)]" aria-label="Your answers">
          {summary.results.map((r) => (
            <li key={r.position} className="flex items-start gap-3 px-4 py-3">
              <span
                className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full text-sm font-bold text-white ${
                  r.correct ? "bg-emerald-500" : "bg-rose-500"
                }`}
                aria-label={r.correct ? "Correct" : "Wrong"}
              >
                {r.correct ? "✓" : "✗"}
              </span>
              <span className="text-sm">{r.prompt}</span>
            </li>
          ))}
        </ol>
      )}

      {!isReview && summary.answered > summary.correct && (
        <p className="text-center text-sm text-muted">
          The ones you missed will come back in your reviews, starting tomorrow.
        </p>
      )}

      <FormError message={start.error ? errorMessage(start.error) : null} />
      <div className="grid gap-3">
        <Button block loading={start.isPending} onClick={playAgain}>
          {isReview ? "Review more" : "Play again"}
        </Button>
        <Link
          to={isReview ? "/" : topicHref}
          className="inline-flex min-h-12 items-center justify-center rounded-xl border border-[var(--line)] font-semibold"
        >
          {isReview ? "Back home" : "Back to topic"}
        </Link>
      </div>
    </div>
  );
}
