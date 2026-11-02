import { Link, useParams } from "react-router";

import { errorMessage } from "../../api/client";
import { useSubject } from "../../api/learn";
import { AccuracyBar, Loading, PageTitle } from "../../components/ui/Bits";
import { FormError } from "../../components/ui/Field";
import { percent } from "../../lib/format";

export function SubjectPage() {
  const subjectId = Number(useParams().subjectId);
  const { data: subject, isPending, error } = useSubject(subjectId);

  if (isPending) return <Loading />;
  if (!subject) return <FormError message={errorMessage(error)} />;

  return (
    <div className="space-y-5">
      <PageTitle back={{ to: "/revise", label: "All subjects" }}>{subject.name}</PageTitle>
      <p className="text-sm text-muted">
        {subject.qualification} · {subject.exam_board}
        {subject.spec_code ? ` · ${subject.spec_code}` : ""}
      </p>
      <ul className="card divide-y divide-[var(--line)] overflow-hidden">
        {subject.topics.map((t) => {
          const playable = t.question_count > 0;
          const body = (
            <>
              <span className="min-w-0 flex-1 space-y-1.5">
                <span className="block font-semibold">
                  {t.spec_ref && <span className="mr-1.5 text-muted">{t.spec_ref}</span>}
                  {t.name}
                </span>
                {t.stats.answered > 0 ? (
                  <span className="flex items-center gap-2 text-xs text-muted">
                    <AccuracyBar accuracy={t.stats.accuracy} />
                    <span className="shrink-0 tabular-nums">{percent(t.stats.accuracy)}</span>
                  </span>
                ) : (
                  <span className="block text-xs text-muted">
                    {playable ? `${t.question_count} questions` : "No questions yet"}
                  </span>
                )}
              </span>
              {playable && <span aria-hidden="true">→</span>}
            </>
          );
          return (
            <li key={t.topic_id}>
              {playable ? (
                <Link
                  to={`/revise/${subject.id}/${t.topic_id}`}
                  className="flex min-h-16 items-center gap-3 px-4 py-3 hover:bg-[var(--surface)]"
                >
                  {body}
                </Link>
              ) : (
                <div className="flex min-h-16 items-center gap-3 px-4 py-3 opacity-60">{body}</div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
