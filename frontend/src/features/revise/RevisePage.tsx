import { Link } from "react-router";

import { errorMessage } from "../../api/client";
import { useHome, useSubjects } from "../../api/learn";
import type { SubjectSummary } from "../../api/types";
import { FormError } from "../../components/ui/Field";
import { Loading, PageTitle } from "../../components/ui/Bits";
import { ReviewCard } from "../progress/ReviewCard";

function SubjectRow({ subject }: { subject: SubjectSummary }) {
  const ready = subject.playable_topic_count > 0;
  return (
    <li>
      <Link
        to={`/revise/${subject.id}`}
        className="flex min-h-16 items-center justify-between gap-3 px-4 py-3 hover:bg-[var(--surface)]"
      >
        <span className="min-w-0">
          <span className="block truncate font-semibold">{subject.name}</span>
          <span className="block truncate text-sm text-muted">
            {subject.qualification} · {subject.exam_board}
          </span>
        </span>
        {ready ? (
          <span className="shrink-0 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300">
            {subject.playable_topic_count} ready
          </span>
        ) : (
          <span className="shrink-0 text-xs text-muted">{subject.topic_count} topics</span>
        )}
      </Link>
    </li>
  );
}

export function RevisePage() {
  const { data: subjects, isPending, error } = useSubjects();
  const home = useHome();
  const ready = subjects?.filter((s) => s.playable_topic_count > 0) ?? [];
  const rest = subjects?.filter((s) => s.playable_topic_count === 0) ?? [];

  return (
    <div className="space-y-5">
      <PageTitle>Revise</PageTitle>
      {home.data && <ReviewCard due={home.data.due_reviews} compact />}
      <Link
        to="/weak-spots"
        className="card flex min-h-14 items-center justify-between px-4 font-semibold hover:border-brand-500"
      >
        <span>📉 Your weak spots</span>
        <span aria-hidden="true">→</span>
      </Link>
      {isPending && <Loading />}
      <FormError message={error ? errorMessage(error) : null} />
      {ready.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Ready to play</h2>
          <ul className="card divide-y divide-[var(--line)] overflow-hidden">
            {ready.map((s) => (
              <SubjectRow key={s.id} subject={s} />
            ))}
          </ul>
        </section>
      )}
      {rest.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Questions coming soon</h2>
          <ul className="card divide-y divide-[var(--line)] overflow-hidden">
            {rest.map((s) => (
              <SubjectRow key={s.id} subject={s} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
