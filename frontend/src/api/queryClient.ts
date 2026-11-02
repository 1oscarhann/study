import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "./client";

/** 502/503 usually means the free-tier server is waking up, so keep trying for a bit. */
export function isWakingUp(error: unknown): boolean {
  return error instanceof ApiError ? error.status === 502 || error.status === 503 : true;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (failureCount, error) => failureCount < 4 && isWakingUp(error),
        retryDelay: (attempt) => Math.min(2000 * 2 ** attempt, 15_000),
        refetchOnWindowFocus: false,
      },
    },
  });
}
