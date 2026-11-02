import { useQuery } from "@tanstack/react-query";

import { api } from "./client";

export interface Health {
  status: string;
  db: string;
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/health"),
    staleTime: 60_000,
  });
}
