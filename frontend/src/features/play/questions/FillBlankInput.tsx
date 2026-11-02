import { useState } from "react";

import type { QuestionInputProps } from "./types";

export function FillBlankInput({ onChange, feedback, onSubmit }: QuestionInputProps) {
  const [text, setText] = useState("");
  const tone = feedback
    ? feedback.correct
      ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-500/15"
      : "border-rose-500 bg-rose-50 dark:bg-rose-500/15"
    : "border-[var(--line)] bg-[var(--card)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30";

  return (
    <div className="space-y-1.5">
      <label htmlFor="blank-answer" className="block text-sm font-semibold">
        Your answer
      </label>
      <input
        id="blank-answer"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          onChange(e.target.value.trim() ? { text: e.target.value } : null);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && text.trim()) {
            e.preventDefault();
            onSubmit?.();
          }
        }}
        disabled={feedback !== null}
        autoComplete="off"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        enterKeyHint="done"
        maxLength={200}
        className={`block min-h-14 w-full rounded-2xl border-2 px-4 text-lg text-[var(--ink)] outline-none ${tone}`}
      />
    </div>
  );
}
