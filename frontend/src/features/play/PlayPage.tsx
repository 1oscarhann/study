import { useState, type JSX } from "react";
import { useNavigate, useParams } from "react-router";

import { errorMessage } from "../../api/client";
import { useAnswer, useEndPlay, usePlay } from "../../api/learn";
import type { AnswerResponse, AnswerResult, ServedQuestion, Summary } from "../../api/types";
import { Splash } from "../../components/guards";
import { Button } from "../../components/ui/Button";
import { FormError } from "../../components/ui/Field";
import { FeedbackPanel } from "./FeedbackPanel";
import { FillBlankInput } from "./questions/FillBlankInput";
import { MatchInput } from "./questions/MatchInput";
import { McqInput } from "./questions/McqInput";
import { OrderInput } from "./questions/OrderInput";
import type { QuestionInputProps } from "./questions/types";
import { ResultsView } from "./ResultsView";

const INPUTS: Record<ServedQuestion["type"], (p: QuestionInputProps) => JSX.Element> = {
  mcq: McqInput,
  fill_blank: FillBlankInput,
  order: OrderInput,
  match: MatchInput,
};

const HINTS: Record<ServedQuestion["type"], string> = {
  mcq: "Pick one answer",
  fill_blank: "Fill in the blank",
  order: "Put these in order",
  match: "Match the pairs",
};

function Prompt({ question }: { question: ServedQuestion }) {
  if (question.type !== "fill_blank") return <>{question.prompt}</>;
  const [before, after] = question.prompt.split("___");
  return (
    <>
      {before}
      <span className="mx-1 inline-block min-w-16 border-b-4 border-brand-500 align-baseline" aria-label="blank">
        &nbsp;
      </span>
      {after}
    </>
  );
}

export function PlayPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const { data: state, isPending, isError, error } = usePlay(sessionId);
  const answer = useAnswer(sessionId);
  const end = useEndPlay(sessionId);

  const [current, setCurrent] = useState<ServedQuestion | null>(null);
  const [response, setResponse] = useState<AnswerResponse | null>(null);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);

  if (isPending) return <Splash />;
  if (isError || !state) {
    return (
      <main className="mx-auto max-w-lg space-y-4 px-4 py-10">
        <FormError message={errorMessage(error)} />
        <Button onClick={() => navigate("/")}>Back home</Button>
      </main>
    );
  }

  const finalSummary = summary ?? state.summary;
  const question = current ?? state.question;
  const progress = result?.progress ?? state.progress;

  if (finalSummary && !result?.summary) {
    return (
      <main className="mx-auto max-w-lg px-4 pb-10 pt-[calc(1.5rem+env(safe-area-inset-top))]">
        <ResultsView summary={finalSummary} />
      </main>
    );
  }
  if (!question) return <Splash />;

  const Input = INPUTS[question.type];
  const feedback = result?.feedback ?? null;

  function check() {
    if (!response || !question || answer.isPending) return;
    answer.mutate({ position: question.position, response }, { onSuccess: setResult });
  }

  function next() {
    if (!result) return;
    if (result.summary) setSummary(result.summary);
    if (result.next) setCurrent(result.next);
    setResult(null);
    setResponse(null);
  }

  function quit() {
    if (window.confirm("End this game? Your answers so far still count.")) {
      end.mutate(undefined, { onSuccess: (s) => setSummary(s) });
    }
  }

  const done = progress.answered;
  const pct = Math.round((done / progress.total) * 100);

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-10 bg-[var(--surface)]/95 px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] backdrop-blur">
        <div className="mx-auto flex max-w-lg items-center gap-3">
          <button
            type="button"
            onClick={quit}
            aria-label="End game"
            className="grid size-10 shrink-0 place-items-center rounded-full text-2xl text-muted hover:bg-[var(--card)]"
          >
            ×
          </button>
          <div
            className="h-3 flex-1 overflow-hidden rounded-full bg-[var(--line)]"
            role="progressbar"
            aria-label="Progress"
            aria-valuemin={0}
            aria-valuemax={progress.total}
            aria-valuenow={done}
          >
            <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${pct}%` }} />
          </div>
          <span className="w-12 text-right text-sm font-semibold tabular-nums text-muted">
            {Math.min(question.position + 1, progress.total)}/{progress.total}
          </span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-lg flex-1 space-y-5 px-4 pb-40 pt-2">
        <div className="space-y-2">
          <p className="text-sm font-semibold text-brand-600 dark:text-brand-400">
            {state.mode === "review" ? `Review · ${question.topic_name}` : HINTS[question.type]}
          </p>
          <h1 className="text-2xl font-bold leading-snug tracking-tight">
            <Prompt question={question} />
          </h1>
        </div>
        <Input
          key={question.position}
          question={question}
          onChange={setResponse}
          feedback={feedback}
          onSubmit={check}
        />
        {feedback && <FeedbackPanel question={question} feedback={feedback} />}
        <FormError message={answer.error ? errorMessage(answer.error) : null} />
      </main>

      <footer className="fixed inset-x-0 bottom-0 border-t border-[var(--line)] bg-[var(--card)]/95 px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-3 backdrop-blur">
        <div className="mx-auto max-w-lg">
          {feedback ? (
            <Button block onClick={next} autoFocus>
              {result?.summary ? "See results" : "Next"}
            </Button>
          ) : (
            <Button block onClick={check} disabled={!response} loading={answer.isPending}>
              Check
            </Button>
          )}
        </div>
      </footer>
    </div>
  );
}
