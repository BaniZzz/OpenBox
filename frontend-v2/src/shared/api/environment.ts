import { useQuery } from "@tanstack/react-query"
import { http } from "@/shared/api/http"

export type EnvironmentName = "" | "dev" | "staging" | "prod"

export interface EnvironmentInfo {
  name: EnvironmentName
}

/** Which deployment this UI is talking to; public, cached for the session. */
export function useEnvironmentQuery() {
  return useQuery({
    queryKey: ["environment"],
    queryFn: () => http.get<EnvironmentInfo>("/api/environment"),
    staleTime: Infinity,
    retry: false,
  })
}
