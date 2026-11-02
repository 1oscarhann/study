import { useState, type FormEvent } from "react";

import { useAddExam, useDeleteExam, useSubjects } from "../../api/learn";
import type { Exam } from "../../api/types";
import { Button } from "../../components/ui/Button";
import { FormError, SelectField, TextField } from "../../components/ui/Field";
import { formErrors } from "../auth/formErrors";
import { daysLeftLabel, shortDate } from "../../lib/format";

function AddExamForm({ onDone }: { onDone: () => void }) {
  const { data: subjects } = useSubjects();
  const add = useAddExam();
  const [subjectId, setSubjectId] = useState("");
  const [date, setDate] = useState("");
  const [label, setLabel] = useState("");
  const errors = formErrors(add.error, ["subject_id", "exam_date", "label"] as const);

  function submit(e: FormEvent) {
    e.preventDefault();
    add.mutate(
      { subject_id: Number(subjectId), exam_date: date, label: label.trim() || null },
      { onSuccess: onDone },
    );
  }

  return (
    <form onSubmit={submit} className="space-y-3 border-t border-[var(--line)] pt-4" noValidate>
      <SelectField label="Subject" value={subjectId} onChange={(e) => setSubjectId(e.target.value)} error={errors.field("subject_id")}>
        <option value="" disabled>
          Choose a subject
        </option>
        {subjects?.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
            {s.qualification !== "GCSE" ? ` (${s.qualification})` : ""}
          </option>
        ))}
      </SelectField>
      <TextField label="Exam date" type="date" value={date} onChange={(e) => setDate(e.target.value)} error={errors.field("exam_date")} />
      <TextField
        label="Label (optional)"
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="Paper 1"
        maxLength={40}
        error={errors.field("label")}
      />
      <FormError message={errors.general} />
      <div className="flex gap-3">
        <Button type="submit" loading={add.isPending} disabled={!subjectId || !date}>
          Add exam
        </Button>
        <Button variant="secondary" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function ExamsCard({ exams }: { exams: Exam[] }) {
  const [adding, setAdding] = useState(false);
  const del = useDeleteExam();

  return (
    <section className="card space-y-3 p-4" aria-labelledby="exams-heading">
      <div className="flex items-center justify-between">
        <h2 id="exams-heading" className="font-bold">
          Exam countdown
        </h2>
        {!adding && (
          <Button variant="ghost" className="!min-h-9 !px-0 text-sm" onClick={() => setAdding(true)}>
            + Add exam
          </Button>
        )}
      </div>
      {exams.length === 0 && !adding && (
        <p className="text-sm text-muted">Add your exam dates to see how many days you've got.</p>
      )}
      {exams.length > 0 && (
        <ul className="space-y-2">
          {exams.map((exam) => (
            <li key={exam.id} className="flex items-center gap-3">
              <span className="grid min-w-16 shrink-0 place-items-center rounded-xl bg-brand-50 px-2 py-1.5 text-center dark:bg-brand-500/15">
                <span className="text-lg font-black leading-none tabular-nums text-brand-700 dark:text-brand-400">
                  {exam.days_left <= 1 ? daysLeftLabel(exam.days_left) : exam.days_left}
                </span>
                {exam.days_left > 1 && <span className="text-[10px] font-semibold uppercase text-muted">days</span>}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-semibold">
                  {exam.subject_name}
                  {exam.label ? ` · ${exam.label}` : ""}
                </span>
                <span className="block text-xs text-muted">{shortDate(exam.exam_date)}</span>
              </span>
              <button
                type="button"
                onClick={() => del.mutate(exam.id)}
                aria-label={`Remove ${exam.subject_name} exam`}
                className="grid size-9 place-items-center rounded-full text-muted hover:bg-[var(--surface)]"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      {adding && <AddExamForm onDone={() => setAdding(false)} />}
    </section>
  );
}
