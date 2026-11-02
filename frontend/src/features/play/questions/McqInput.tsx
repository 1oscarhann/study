import { useState } from "react";

import type { QuestionInputProps } from "./types";

export function McqInput({ question, onChange, feedback }: QuestionInputProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const correctId = feedback ? (feedback.correct_answer.option_id as string) : null;

  return (
    <div role="radiogroup" aria-label="Answers" className="space-y-3">
      {(question.options ?? []).map((option, i) => {
        const isSelected = selected === option.id;
        let tone = "border-[var(--line)] bg-[var(--card)]";
        if (feedback) {
          if (option.id === correctId) tone = "border-emerald-500 bg-emerald-50 dark:bg-emerald-500/15";
          else if (isSelected) tone = "border-rose-500 bg-rose-50 dark:bg-rose-500/15";
          else tone = "border-[var(--line)] bg-[var(--card)] opacity-60";
        } else if (isSelected) {
          tone = "border-brand-500 bg-brand-50 ring-2 ring-brand-500/30 dark:bg-brand-500/15";
        }
        return (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={isSelected}
            disabled={feedback !== null}
            onClick={() => {
              setSelected(option.id);
              onChange({ option_id: option.id });
            }}
            className={`flex min-h-14 w-full items-center gap-3 rounded-2xl border-2 px-4 py-3 text-left text-base font-medium transition-colors ${tone}`}
          >
            <span
              className="grid size-7 shrink-0 place-items-center rounded-full border border-current text-sm font-bold text-muted"
              aria-hidden="true"
            >
              {String.fromCharCode(65 + i)}
            </span>
            <span>{option.text}</span>
          </button>
        );
      })}
    </div>
  );
}
