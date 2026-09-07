import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { http } from "./http"
import { useAuthStore } from "./auth-store"
import { useWorkspaceStore } from "./workspace-store"

export interface DesktopStatus {
  mode?: string
  state: string
  entitled?: boolean
  retained?: boolean
  subscription_ends_at?: string | null
  desktopId?: string | null
  error?: string
  channel?: { state: string; error?: string; last_seen_at?: string | null }
  activation?: {
    request_id: string | null
    state: string
    step: string
    attempts: number
    error: string | null
    updated_at: string
    next_retry_at: string
    can_retry: boolean
  } | null
}

export function useDesktopScope() {
  const userId = useAuthStore((s) => s.user?.id)
  const workspaceId = useWorkspaceStore((s) => s.currentId)
  return {
    // Billing settlement invalidation refreshes this immediately too.
    key: ["billing", userId, workspaceId, "desktop"] as const,
    enabled: Boolean(userId && workspaceId),
    options: { headers: { "X-Workspace-Id": workspaceId ?? "" } },
  }
}

export function useDesktopStatus() {
  const scope = useDesktopScope()
  return useQuery({
    queryKey: scope.key,
    enabled: scope.enabled,
    queryFn: ({ signal }) => http.get<DesktopStatus>("/api/desktop/status", { ...scope.options, signal }),
    retry: false,
    refetchOnMount: "always",
    refetchInterval: (query) => {
      const state = query.state.data?.state
      return state && !["running", "subscription_required"].includes(state) ? 3_000 : 15_000
    },
  })
}

export function useRetryDesktop() {
  const scope = useDesktopScope()
  const client = useQueryClient()
  return useMutation({
    mutationFn: () => http.post<DesktopStatus>("/api/desktop/provision", undefined, scope.options),
    onSuccess: (data) => client.setQueryData(scope.key, data),
    onSettled: () => void client.invalidateQueries({ queryKey: scope.key }),
  })
}
