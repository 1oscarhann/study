import type { components } from "./schema";

type Schemas = components["schemas"];

export type Me = Schemas["MeResponse"];
export type AuthResponse = Schemas["AuthResponse"];
export type AuthWithRecoveryCode = Schemas["AuthWithRecoveryCodeResponse"];
export type SignupRequest = Schemas["SignupRequest"];
export type LoginRequest = Schemas["LoginRequest"];
export type RecoverRequest = Schemas["RecoverRequest"];
export type ChangePasswordRequest = Schemas["ChangePasswordRequest"];
export type RecoveryCodeResponse = Schemas["RecoveryCodeResponse"];
export type UsernameIdeas = Schemas["UsernameIdeasResponse"];

export type SubjectSummary = Schemas["SubjectSummary"];
export type SubjectDetail = Schemas["SubjectDetail"];
export type TopicSummary = Schemas["TopicSummary"];
export type TopicDetail = Schemas["TopicDetail"];
export type PlayState = Schemas["PlayState"];
export type ServedQuestion = Schemas["ServedQuestion"];
export type Choice = Schemas["Choice"];
export type AnswerResult = Schemas["AnswerResult"];
export type Feedback = Schemas["Feedback"];
export type Summary = Schemas["Summary"];
export type Home = Schemas["Home"];
export type WeakSpots = Schemas["WeakSpots"];
export type WeakSpot = Schemas["WeakSpot"];
export type Exam = Schemas["Exam"];
export type ExamIn = Schemas["ExamIn"];
// include_higher has a server default (true), so it is optional when sending.
export type StartPlayRequest = Omit<Schemas["StartPlayRequest"], "include_higher"> & { include_higher?: boolean };

/** What the player sends back, by question type. */
export type AnswerResponse =
  | { option_id: string }
  | { text: string }
  | { order: string[] }
  | { pairs: Record<string, string> };
