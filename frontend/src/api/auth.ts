import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, ApiError } from "./client";
import type {
  AuthResponse,
  AuthWithRecoveryCode,
  ChangePasswordRequest,
  LoginRequest,
  Me,
  RecoverRequest,
  RecoveryCodeResponse,
  SignupRequest,
  UsernameIdeas,
} from "./types";

export const ME_KEY = ["me"] as const;

/** The logged-in user, or null when logged out (a 401 isn't an error here). */
export async function fetchMe(): Promise<Me | null> {
  try {
    return await api<Me>("/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export function useMe() {
  return useQuery({ queryKey: ME_KEY, queryFn: fetchMe, staleTime: 5 * 60_000 });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: LoginRequest) => api<AuthResponse>("/auth/login", { method: "POST", json: body }),
    onSuccess: (data) => queryClient.setQueryData(ME_KEY, data.user),
  });
}

/**
 * Signup and recovery return a recovery code that must be shown before moving on, so
 * these don't update the cached user themselves; call `finishAuth` once it's been seen.
 */
export function useSignup() {
  return useMutation({
    mutationFn: (body: SignupRequest) =>
      api<AuthWithRecoveryCode>("/auth/signup", { method: "POST", json: body }),
  });
}

export function useRecover() {
  return useMutation({
    mutationFn: (body: RecoverRequest) =>
      api<AuthWithRecoveryCode>("/auth/recover", { method: "POST", json: body }),
  });
}

export function useFinishAuth() {
  const queryClient = useQueryClient();
  return (user: Me) => queryClient.setQueryData(ME_KEY, user);
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api<void>("/auth/logout", { method: "POST" }),
    onSettled: () => {
      queryClient.clear();
      queryClient.setQueryData(ME_KEY, null);
    },
  });
}

export function useUsernameIdeas() {
  return useMutation({ mutationFn: () => api<UsernameIdeas>("/auth/username-ideas") });
}

export function useChangeYearGroup() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (yearGroup: number) =>
      api<Me>("/me/year-group", { method: "PATCH", json: { year_group: yearGroup } }),
    onSuccess: (me) => queryClient.setQueryData(ME_KEY, me),
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: ChangePasswordRequest) => api<void>("/me/password", { method: "POST", json: body }),
  });
}

export function useNewRecoveryCode() {
  return useMutation({
    mutationFn: (password: string) =>
      api<RecoveryCodeResponse>("/me/recovery-code", { method: "POST", json: { password } }),
  });
}

export function useDeleteAccount() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => api<void>("/me", { method: "DELETE", json: { password } }),
    onSuccess: () => {
      queryClient.clear();
      queryClient.setQueryData(ME_KEY, null);
    },
  });
}
