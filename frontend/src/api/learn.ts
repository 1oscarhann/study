import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router";

import { api } from "./client";
import type {
  AnswerResponse,
  AnswerResult,
  Exam,
  ExamIn,
  Home,
  PlayState,
  StartPlayRequest,
  SubjectDetail,
  SubjectSummary,
  Summary,
  TopicDetail,
  WeakSpots,
} from "./types";

export const keys = {
  subjects: ["subjects"] as const,
  subject: (id: number) => ["subject", id] as const,
  topic: (id: number, subjectId: number | null) => ["topic", id, subjectId] as const,
  play: (id: string) => ["play", id] as const,
  home: ["home"] as const,
  weakSpots: ["weak-spots"] as const,
  exams: ["exams"] as const,
};

export function useSubjects() {
  return useQuery({
    queryKey: keys.subjects,
    queryFn: async () => (await api<{ subjects: SubjectSummary[] }>("/subjects")).subjects,
    staleTime: 5 * 60_000,
  });
}

export function useSubject(id: number) {
  return useQuery({ queryKey: keys.subject(id), queryFn: () => api<SubjectDetail>(`/subjects/${id}`) });
}

export function useTopic(id: number, subjectId: number | null) {
  return useQuery({
    queryKey: keys.topic(id, subjectId),
    queryFn: () => api<TopicDetail>(`/topics/${id}${subjectId ? `?subject_id=${subjectId}` : ""}`),
  });
}

/** Start a quiz or review and jump straight into it. */
export function useStartPlay() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: (body: StartPlayRequest) => api<PlayState>("/play", { method: "POST", json: body }),
    onSuccess: (state) => {
      queryClient.setQueryData(keys.play(state.session_id), state);
      navigate(`/play/${state.session_id}`);
    },
  });
}

export function usePlay(id: string) {
  return useQuery({
    queryKey: keys.play(id),
    queryFn: () => api<PlayState>(`/play/${id}`),
    staleTime: Infinity, // the runner keeps its own state; never refetch mid-question
  });
}

/**
 * Anything a finished game changes: stats, due counts, quick launch. Reset (not just
 * invalidate) so pages show a loading state instead of briefly flashing old numbers.
 */
function invalidateProgress(queryClient: ReturnType<typeof useQueryClient>) {
  for (const key of [keys.home, keys.weakSpots, ["subject"], ["topic"]]) {
    void queryClient.resetQueries({ queryKey: key });
  }
}

export function useAnswer(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { position: number; response: AnswerResponse }) =>
      api<AnswerResult>(`/play/${sessionId}/answer`, { method: "POST", json: body }),
    onSuccess: (result) => {
      if (result.summary) invalidateProgress(queryClient);
    },
  });
}

export function useEndPlay(sessionId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api<Summary>(`/play/${sessionId}/end`, { method: "POST" }),
    onSuccess: () => invalidateProgress(queryClient),
  });
}

export function useHome() {
  return useQuery({ queryKey: keys.home, queryFn: () => api<Home>("/home") });
}

export function useWeakSpots() {
  return useQuery({ queryKey: keys.weakSpots, queryFn: () => api<WeakSpots>("/progress/weak-spots") });
}

export function useExams() {
  return useQuery({
    queryKey: keys.exams,
    queryFn: async () => (await api<{ exams: Exam[] }>("/exams")).exams,
  });
}

export function useAddExam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ExamIn) => api<Exam>("/exams", { method: "POST", json: body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.exams });
      void queryClient.invalidateQueries({ queryKey: keys.home });
    },
  });
}

export function useDeleteExam() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api<void>(`/exams/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.exams });
      void queryClient.invalidateQueries({ queryKey: keys.home });
    },
  });
}
