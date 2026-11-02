import type { Home, PlayState, ServedQuestion, SubjectDetail, SubjectSummary, TopicDetail } from "../api/types";

export const SESSION = "11111111-2222-3333-4444-555555555555";

export const EMPTY_HOME: Home = {
  user: { username: "SwiftOtter42", year_group: 10, graduated: false, total_xp: 0, streak_current: 0 },
  due_reviews: { today: 0, this_week: 0 },
  recent_topics: [],
  weakest_topic: null,
  exams: [],
};

export const SUBJECTS: SubjectSummary[] = [
  { id: 1, slug: "biology", name: "Biology", qualification: "GCSE (triple)", exam_board: "AQA", topic_count: 7, playable_topic_count: 1 },
  { id: 2, slug: "mathematics", name: "Mathematics", qualification: "GCSE", exam_board: "Edexcel / AQA", topic_count: 6, playable_topic_count: 0 },
];

export const BIOLOGY: SubjectDetail = {
  id: 1, slug: "biology", name: "Biology", qualification: "GCSE (triple)", exam_board: "AQA", spec_code: "8461",
  topics: [
    { topic_id: 10, slug: "sci-bio-cells", name: "Cell biology", spec_ref: "4.1", question_count: 25,
      stats: { answered: 10, correct: 7, accuracy: 0.7 }, last_played_at: null },
    { topic_id: 11, slug: "sci-bio-organisation", name: "Organisation", spec_ref: "4.2", question_count: 0,
      stats: { answered: 0, correct: 0, accuracy: null }, last_played_at: null },
  ],
};

export const CELLS: TopicDetail = {
  topic_id: 10, slug: "sci-bio-cells", name: "Cell biology", subject_id: 1, subject_name: "Biology", spec_ref: "4.1",
  subtopics: [{ name: "Microscopy and magnification", higher_only: false, triple_only: false }],
  learn_more_url: "https://en.wikipedia.org/wiki/Cell_(biology)",
  question_count: 25, higher_only_count: 4, due_count: 2,
  stats: { answered: 10, correct: 7, accuracy: 0.7 }, last_played_at: null,
};

export const MCQ: ServedQuestion = {
  position: 0, question_id: 101, type: "mcq", prompt: "Where does aerobic respiration take place?",
  subtopic: null, topic_name: "Cell biology",
  options: [{ id: "a", text: "Ribosomes" }, { id: "b", text: "Mitochondria" }, { id: "c", text: "Nucleus" }],
};

export const FILL: ServedQuestion = {
  position: 1, question_id: 102, type: "fill_blank", prompt: "Plant cell walls are made of ___.",
  subtopic: null, topic_name: "Cell biology",
};

export const ORDER: ServedQuestion = {
  position: 0, question_id: 103, type: "order", prompt: "Put these in order.", subtopic: null, topic_name: "Weimar",
  items: [{ id: "c", text: "Third" }, { id: "a", text: "First" }, { id: "b", text: "Second" }],
};

export const MATCH: ServedQuestion = {
  position: 0, question_id: 104, type: "match", prompt: "Match each particle.", subtopic: null, topic_name: "Atoms",
  left: [{ id: "la", text: "Proton" }, { id: "lb", text: "Electron" }],
  right: [{ id: "rb", text: "Charge −1" }, { id: "ra", text: "Charge +1" }],
};

export function playState(question: ServedQuestion, total = 2): PlayState {
  return {
    session_id: SESSION, mode: "quiz", status: "active", topic: { id: 10, name: "Cell biology" }, subject_id: 1,
    progress: { answered: 0, correct: 0, total }, question, summary: null,
  };
}
