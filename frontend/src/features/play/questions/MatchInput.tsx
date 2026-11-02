import { useState } from "react";

import { PAIR_COLOURS, type QuestionInputProps } from "./types";

/** Tap a term, then tap its definition. Matching pairs share a coloured number. */
export function MatchInput({ question, onChange, feedback }: QuestionInputProps) {
  const left = question.left ?? [];
  const right = question.right ?? [];
  const [pairs, setPairs] = useState<Record<string, string>>({});
  const [active, setActive] = useState<string | null>(left[0]?.id ?? null);
  const correct = feedback ? (feedback.correct_answer.pairs as Record<string, string>) : null;

  const colourOf = (leftId: string) => PAIR_COLOURS[left.findIndex((l) => l.id === leftId) % PAIR_COLOURS.length];
  const leftFor = (rightId: string) => Object.keys(pairs).find((k) => pairs[k] === rightId) ?? null;

  function choose(rightId: string) {
    if (!active) return;
    const next = { ...pairs };
    const previousOwner = leftFor(rightId);
    if (previousOwner) delete next[previousOwner]; // a definition can only be used once
    next[active] = rightId;
    setPairs(next);
    onChange(Object.keys(next).length === left.length ? { pairs: next } : null);
    setActive(left.find((l) => !(l.id in next))?.id ?? null);
  }

  return (
    <div className="space-y-5">
      <div>
        <p className="mb-2 text-sm font-semibold">1. Tap a term</p>
        <ul className="flex flex-wrap gap-2">
          {left.map((term, i) => {
            const paired = term.id in pairs;
            const isActive = active === term.id && !feedback;
            const verdict = correct ? correct[term.id] === pairs[term.id] : null;
            return (
              <li key={term.id}>
                <button
                  type="button"
                  disabled={feedback !== null}
                  aria-pressed={isActive}
                  onClick={() => setActive(term.id)}
                  className={`flex min-h-11 items-center gap-2 rounded-full border-2 px-3 py-1.5 font-semibold ${
                    verdict === null
                      ? isActive
                        ? "border-brand-500 bg-brand-50 dark:bg-brand-500/15"
                        : "border-[var(--line)] bg-[var(--card)]"
                      : verdict
                        ? "border-emerald-500"
                        : "border-rose-500"
                  }`}
                >
                  {paired && (
                    <span className={`grid size-6 place-items-center rounded-full text-xs font-bold text-white ${colourOf(term.id)}`}>
                      {i + 1}
                    </span>
                  )}
                  {term.text}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
      <div>
        <p className="mb-2 text-sm font-semibold">2. Tap what it matches</p>
        <ul className="space-y-2">
          {right.map((definition) => {
            const owner = leftFor(definition.id);
            const ownerIndex = owner ? left.findIndex((l) => l.id === owner) : -1;
            return (
              <li key={definition.id}>
                <button
                  type="button"
                  disabled={feedback !== null || !active}
                  onClick={() => choose(definition.id)}
                  className={`flex min-h-12 w-full items-center gap-3 rounded-2xl border-2 px-4 py-2.5 text-left ${
                    owner ? "border-transparent bg-[var(--surface)]" : "border-[var(--line)] bg-[var(--card)] hover:border-brand-500"
                  }`}
                >
                  <span
                    className={`grid size-6 shrink-0 place-items-center rounded-full text-xs font-bold text-white ${
                      owner ? colourOf(owner) : "bg-transparent"
                    }`}
                    aria-hidden={!owner}
                  >
                    {owner ? ownerIndex + 1 : ""}
                  </span>
                  <span>{definition.text}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
