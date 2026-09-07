import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { useAuthStore } from "@/shared/api/auth-store"
import { useWorkspaceStore } from "@/shared/api/workspace-store"
import { http } from "@/shared/api/http"
import type { DesktopStatus } from "@/shared/api/desktop"
import { DesktopActivationDialog } from "./DesktopActivationDialog"

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock("@/shared/api/http", () => ({ http: { get: vi.fn(), post: vi.fn() } }))

const clients: QueryClient[] = []
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  clients.push(client)
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <DesktopActivationDialog />
      </QueryClientProvider>,
    ),
  }
}

function progress(step = "assigning", requestId = "payment-1"): DesktopStatus {
  return {
    mode: "per_user",
    state: step === "ready" ? "running" : step,
    entitled: true,
    activation: {
      request_id: requestId,
      state: step === "ready" ? "ready" : "working",
      step,
      attempts: 1,
      error: null,
      updated_at: "2026-09-07T00:00:00Z",
      next_retry_at: "2026-09-07T00:00:30Z",
      can_retry: false,
    },
  }
}

beforeEach(() => {
  localStorage.clear()
  useAuthStore.setState({
    user: { id: "user", username: "user", role: "user" } as NonNullable<
      ReturnType<typeof useAuthStore.getState>["user"]
    >,
  })
  useWorkspaceStore.setState({ currentId: "workspace", items: [] })
  Object.defineProperty(HTMLDialogElement.prototype, "showModal", {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.setAttribute("open", "")
    },
  })
  Object.defineProperty(HTMLDialogElement.prototype, "close", {
    configurable: true,
    value: function (this: HTMLDialogElement) {
      this.removeAttribute("open")
    },
  })
  vi.mocked(http.get).mockResolvedValue(progress())
})

afterEach(() => {
  cleanup()
  clients.splice(0).forEach((client) => client.clear())
  vi.restoreAllMocks()
  vi.resetAllMocks()
})

describe("DesktopActivationDialog", () => {
  it("opens automatically from server state without provisioning from the browser", async () => {
    mount()
    const dialog = await screen.findByRole("dialog")
    expect(dialog.getAttribute("open")).toBe("")
    expect(dialog.querySelector('[aria-current="step"]')?.textContent).toContain("activation.steps.assigning")
    expect(http.post).not.toHaveBeenCalled()
    expect(http.get).toHaveBeenCalledWith(
      "/api/desktop/status",
      expect.objectContaining({ headers: { "X-Workspace-Id": "workspace" } }),
    )
  })

  it("does not open for free accounts, even when their machine is retained", async () => {
    vi.mocked(http.get).mockResolvedValue({
      ...progress(),
      state: "subscription_required",
      entitled: false,
      retained: true,
    })
    const { client } = mount()
    await waitFor(() => expect(client.isFetching()).toBe(0))
    expect(screen.queryByRole("dialog")).toBeNull()
    expect(http.post).not.toHaveBeenCalled()
  })

  it("can close and reopen progress, and restores it after a browser reload", async () => {
    const first = mount()
    await screen.findByRole("dialog")
    fireEvent.click(screen.getByText("activation.continueChat"))
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    fireEvent.click(screen.getByText("activation.viewProgress"))
    await screen.findByRole("dialog")
    first.unmount()
    vi.mocked(http.get).mockResolvedValue(progress("connecting"))
    mount()
    const dialog = await screen.findByRole("dialog")
    expect(dialog.querySelector('[aria-current="step"]')?.textContent).toContain(
      "activation.steps.connecting",
    )
  })

  it("shows completion even after dismissing preparation and acknowledges it once", async () => {
    const first = mount()
    await screen.findByRole("dialog")
    fireEvent.click(screen.getByText("activation.continueChat"))
    vi.mocked(http.get).mockResolvedValue(progress("ready"))
    await act(async () => {
      await first.client.invalidateQueries()
    })
    await screen.findByRole("dialog")
    expect(screen.getByText("activation.ready")).toBeTruthy()
    fireEvent.click(screen.getByText("activation.done"))
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    first.unmount()
    const second = mount()
    await waitFor(() => expect(second.client.isFetching()).toBe(0))
    expect(screen.queryByRole("dialog")).toBeNull()
  })

  it("keeps the saved stage visible while the server is temporarily offline", async () => {
    const { client } = mount()
    await screen.findByRole("dialog")
    vi.mocked(http.get).mockRejectedValue(new Error("offline"))
    await act(async () => {
      await client.refetchQueries()
    })
    await screen.findByText("activation.reconnecting")
    expect(screen.getByRole("dialog").querySelector('[aria-current="step"]')?.textContent).toContain(
      "activation.steps.assigning",
    )
  })

  it("never shows another workspace's progress after switching", async () => {
    mount()
    await screen.findByRole("dialog")
    vi.mocked(http.get).mockResolvedValue({
      state: "subscription_required",
      mode: "per_user",
      entitled: false,
    })
    act(() => useWorkspaceStore.setState({ currentId: "other" }))
    await waitFor(() =>
      expect(http.get).toHaveBeenLastCalledWith(
        "/api/desktop/status",
        expect.objectContaining({ headers: { "X-Workspace-Id": "other" } }),
      ),
    )
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
  })
})
