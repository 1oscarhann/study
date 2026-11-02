import type { AnswerResponse, Feedback, ServedQuestion } from "../../../api/types";

export interface QuestionInputProps {
  question: ServedQuestion;
  /** Called with a complete answer, or null while it's still incomplete. */
  onChange: (response: AnswerResponse | null) => void;
  /** Set once answered: inputs lock and show what was right/wrong. */
  feedback: Feedback | null;
  /** Lets fill-the-blank submit on Enter. */
  onSubmit?: () => void;
}

export const PAIR_COLOURS = [
  "bg-sky-500",
  "bg-amber-500",
  "bg-fuchsia-500",
  "bg-emerald-500",
  "bg-orange-500",
  "bg-indigo-500",
];
