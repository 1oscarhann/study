import { useState } from "react";

import type { QuestionInputProps } from "./types";

/** Tap the items in order; tap a placed one to take it back. */
export function OrderInput({ question, onChange, feedback }: QuestionInputProps) {
  const items = question.items ?? [];
  const [placed, setPlaced] = useState<string[]>([]);
  const byId = Object.fromEntries(items.map((i) => [i.id, i.text]));
  const correctOrder = feedback ? (feedback.correct_answer.order as string[]) : null;

  function update(next: string[]) {
    setPlaced(next);
    onChange(next.length === items.length ? { order: next } : null);
  }

  return (
    <div className="space-y-4">
      <div>
        <p className="mb-2 text-sm font-semibold">Your order</p>
        <ol className="space-y-2" aria-label="Your order">
          {placed.length === 0 && (
            <li className="rounded-2xl border-2 border-dashed border-[var(--line)] px-4 py-4 text-sm text-muted">
              Tap the items below, first to last.
            </li>
          )}
          {placed.map((id, index) => {
            const right = correctOrder ? correctOrder[index] === id : null;
            const tone =
              right === null
                ? "border-brand-500 bg-brand-50 dark:bg-brand-500/15"
                : right
                  ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-500/15"
                  : "border-rose-500 bg-rose-50 dark:bg-rose-500/15";
            return (
              <li key={id}>
                <button
                  type="button"
                  disabled={feedback !== null}
                  onClick={() => update(placed.filter((p) => p !== id))}
                  aria-label={`${index + 1}. ${byId[id]} (tap to remove)`}
                  className={`flex min-h-12 w-full items-center gap-3 rounded-2xl border-2 px-4 py-2.5 text-left font-medium ${tone}`}
                >
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-600 text-sm font-bold text-white">
                    {index + 1}
                  </span>
                  {byId[id]}
                </button>
              </li>
            );
          })}
        </ol>
      </div>
      {placed.length < items.length && !feedback && (
        <div>
          <p className="mb-2 text-sm font-semibold">Tap next</p>
          <ul className="space-y-2">
            {items
              .filter((i) => !placed.includes(i.id))
              .map((item) => (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => update([...placed, item.id])}
                    className="flex min-h-12 w-full items-center rounded-2xl border-2 border-[var(--line)] bg-[var(--card)] px-4 py-2.5 text-left font-medium hover:border-brand-500"
                  >
                    {item.text}
                  </button>
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}
