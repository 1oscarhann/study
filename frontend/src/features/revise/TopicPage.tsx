import { useState } from "react";
import { useParams } from "react-router";

import { errorMessage } from "../../api/client";
import { useStartPlay, useTopic } from "../../api/learn";
import { AccuracyBar, Loading, PageTitle } from "../../components/ui/Bits";
import { Button } from "../../components/ui/Button";
import { FormError } from "../../components/ui/Field";
import { percent } from "../../lib/format";
import { getIncludeHigher, setIncludeHigher } from "../../lib/tier";

export function TopicPage() {
  const params = useParams();
  const subjectId = Number(params.subjectId);
  const topicId = Number(params.topicId);
  const { data: topic, isPending, error } = useTopic(topicId, subjectId);
  const start = useStartPlay();
  const [higher, setHigher] = useState(() => getIncludeHigher(subjectId));

  if (isPending) return <Loading />;
  if (!topic) return <FormError message={errorMessage(error)} />;

  function chooseTier(includeHigher: boolean) {
    setHigher(includeHigher);
    setIncludeHigher(subjectId, includeHigher);
  }

  return (
    <div className="space-y-5">
      <PageTitle back={{ to: `/revise/${subjectId}`, label: topic.subject_name ?? "Back" }}>{topic.name}</PageTitle>

      <section className="card grid grid-cols-3 divide-x divide-[var(--line)] text-center" aria-label="Your progress">
        <div className="p-3">
          <p className="text-2xl font-bold tabular-nums">{percent(topic.stats.accuracy)}</p>
          <p className="text-xs text-muted">accuracy</p>
        </div>
        <div className="p-3">
          <p className="text-2xl font-bold tabular-nums">{topic.stats.answered}</p>
          <p className="text-xs text-muted">answered</p>
        </div>
        <div className="p-3">
          <p className="text-2xl font-bold tabular-nums">{topic.due_count}</p>
          <p className="text-xs text-muted">due today</p>
        </div>
        {topic.stats.answered > 0 && (
          <div className="col-span-3 border-t border-[var(--line)] p-3">
            <AccuracyBar accuracy={topic.stats.accuracy} />
          </div>
        )}
      </section>

      {topic.higher_only_count > 0 && (
        <fieldset className="card flex items-center gap-2 p-2">
          <legend className="sr-only">Tier</legend>
          {[
            { label: "Foundation", value: false },
            { label: "Higher", value: true },
          ].map((opt) => (
            <label
              key={opt.label}
              className={`flex min-h-11 flex-1 cursor-pointer items-center justify-center rounded-xl font-semibold ${
                higher === opt.value ? "bg-brand-600 text-white" : "text-muted"
              }`}
            >
              <input
                type="radio"
                name="tier"
                className="sr-only"
                checked={higher === opt.value}
                onChange={() => chooseTier(opt.value)}
              />
              {opt.label}
            </label>
          ))}
        </fieldset>
      )}

      {topic.question_count > 0 ? (
        <div className="grid gap-3">
          <Button
            block
            loading={start.isPending}
            onClick={() =>
              start.mutate({ mode: "quiz", topic_id: topicId, subject_id: subjectId, include_higher: higher })
            }
          >
            ⚡ Quick quiz · {Math.min(10, topic.question_count)} questions
          </Button>
          <Button block variant="secondary" disabled>
            🤖 Bot battle (coming soon)
          </Button>
          <Button block variant="secondary" disabled>
            👾 Boss battle (coming soon)
          </Button>
        </div>
      ) : (
        <p className="card p-4 text-muted">
          There aren't any questions for this topic yet. Soon you'll be able to make your own set from your
          notes in the Create tab.
        </p>
      )}
      <FormError message={start.error ? errorMessage(start.error) : null} />

      {topic.subtopics.length > 0 && (
        <details className="card p-4">
          <summary className="cursor-pointer font-semibold">What this topic covers</summary>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">
            {topic.subtopics.map((s) => (
              <li key={s.name}>
                {s.name}
                {s.higher_only && <span className="ml-1 text-xs text-muted">(Higher)</span>}
                {s.triple_only && <span className="ml-1 text-xs text-muted">(Triple only)</span>}
              </li>
            ))}
          </ul>
        </details>
      )}
      {topic.learn_more_url && (
        <a
          href={topic.learn_more_url}
          target="_blank"
          rel="noopener noreferrer"
          className="block text-sm font-semibold text-brand-600 underline underline-offset-4 dark:text-brand-400"
        >
          Learn more about this topic ↗
        </a>
      )}
    </div>
  );
}
