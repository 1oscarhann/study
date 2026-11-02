import { useEffect, useRef } from "react";

import type { Feedback, ServedQuestion } from "../../api/types";
import { comesBackIn } from "../../lib/format";

function CorrectAnswer({ question, feedback }: { question: ServedQuestion; feedback: Feedback }) {
  const answer = feedback.correct_answer;
  switch (question.type) {
    case "mcq":
    case "fill_blank":
      return (
        <p>
          <span className="font-semibold">Answer:</span> {answer.text as string}
        </p>
      );
    case "order":
      return (
        <div>
          <p className="font-semibold">Correct order:</p>
          <ol className="ml-5 list-decimal">
            {(answer.texts as string[]).map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ol>
        </div>
      );
    case "match":
      return (
        <div>
          <p className="font-semibold">Correct pairs:</p>
          <ul className="space-y-1">
            {(answer.texts as [string, string][]).map(([a, b]) => (
              <li key={a}>
                <strong>{a}</strong> → {b}
              </li>
            ))}
          </ul>
        </div>
      );
  }
}

export function FeedbackPanel({ question, feedback }: { question: ServedQuestion; feedback: Feedback }) {
  const good = feedback.correct;
  const ref = useRef<HTMLElement>(null);
  // On small phones the explanation lands below the fold; bring it into view.
  useEffect(() => {
    ref.current?.scrollIntoView?.({ behavior: "smooth", block: "nearest" });
  }, []);
  return (
    <section
      ref={ref}
      role="status"
      aria-live="polite"
      className={`scroll-mb-32 space-y-3 rounded-2xl p-4 ${
        good ? "bg-emerald-50 text-emerald-950 dark:bg-emerald-500/15 dark:text-emerald-100" : "bg-rose-50 text-rose-950 dark:bg-rose-500/15 dark:text-rose-100"
      }`}
    >
      <h2 className="text-xl font-bold">{good ? "Correct!" : "Not quite"}</h2>
      {feedback.partial && <p className="text-sm font-medium">{feedback.partial}.</p>}
      {!good && <CorrectAnswer question={question} feedback={feedback} />}
      <p>{feedback.explanation}</p>
      {feedback.learn_more_url && (
        <a
          href={feedback.learn_more_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block font-semibold underline underline-offset-4"
        >
          Learn more about this topic ↗
        </a>
      )}
      {feedback.review && !good && <p className="text-sm opacity-80">{comesBackIn(feedback.review.days_until_due)}</p>}
    </section>
  );
}
