// Isolated visual fixture. No real login, payment, desktop, or backend is used.
import { Suspense } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { DesktopActivationDialog } from "../../src/features/workbench/components/DesktopActivationDialog"
import { useAuthStore } from "../../src/shared/api/auth-store"
import { useWorkspaceStore } from "../../src/shared/api/workspace-store"
import "../../src/styles/index.css"
import "../../src/shared/i18n"

useAuthStore.setState({
  user: { id: "fixture-user", username: "fixture-user", role: "user" } as NonNullable<
    ReturnType<typeof useAuthStore.getState>["user"]
  >,
})
useWorkspaceStore.setState({
  currentId: "fixture-workspace",
  items: [
    {
      id: "fixture-workspace",
      name: "我的工作空间",
      owner_user_id: "fixture-user",
      kind: "personal",
      role: "owner",
    },
  ],
})
const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={client}>
    <main className="bg-bg text-ink flex min-h-screen items-center justify-center">
      <div className="border-hair bg-card rounded-2xl border p-10">OpenBox</div>
    </main>
    <Suspense fallback={null}>
      <DesktopActivationDialog />
    </Suspense>
  </QueryClientProvider>,
)
