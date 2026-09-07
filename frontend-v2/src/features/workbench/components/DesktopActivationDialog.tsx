import { useEffect, useId, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { Check, Monitor, X } from "lucide-react"
import { useDesktopScope, useDesktopStatus, useRetryDesktop, type DesktopStatus } from "@/shared/api/desktop"
import { useWorkspaceStore } from "@/shared/api/workspace-store"
import { Spinner } from "@/shared/ui/Spinner"
import { cn } from "@/shared/lib/cn"

const steps = ["paid", "assigning", "starting", "connecting", "ready"] as const
const positions: Record<string, number> = {
  queued: 1,
  assigning: 1,
  creating: 1,
  starting: 2,
  connecting: 3,
  ready: 4,
}

function acknowledged(key: string, requestId: string | null | undefined) {
  try {
    return Boolean(requestId && localStorage.getItem(key) === requestId)
  } catch {
    return false
  }
}

function progressState(data?: DesktopStatus) {
  const job = data?.activation
  const ready = data?.state === "running"
  const attention = job?.state === "needs_attention"
  return {
    job,
    ready,
    attention,
    active: data?.mode === "per_user" && data.entitled === true && Boolean(job?.request_id),
    position: ready ? 4 : (positions[job?.step ?? "queued"] ?? 1),
    title: ready ? "activation.ready" : attention ? "activation.attention" : "activation.title",
    message: attention
      ? "activation.attentionHint"
      : job?.state === "retrying"
        ? "activation.retrying"
        : null,
  }
}

export function DesktopActivationDialog() {
  const scope = useDesktopScope()
  // Switching accounts/workspaces must discard dismissed state and old requests.
  return <ScopedActivationDialog key={JSON.stringify(scope.key)} />
}

function ScopedActivationDialog() {
  const { t } = useTranslation("workbench")
  const query = useDesktopStatus()
  const retry = useRetryDesktop()
  const scope = useDesktopScope()
  const workspace = useWorkspaceStore((s) => s.items.find((w) => w.id === s.currentId))
  const name = workspace?.name ?? ""
  const canManage = workspace?.role === "owner" || workspace?.role === "admin"
  const dialog = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const bodyId = useId()
  const [dismissed, setDismissed] = useState("")
  const { job, ready, attention, active, position, title, message } = progressState(query.data)
  const storageKey = `openbox:desktop-ready:${JSON.stringify(scope.key)}`
  const visibilityKey = `${job?.request_id}:${ready ? "ready" : "pending"}`
  const open =
    active && dismissed !== visibilityKey && !acknowledged(storageKey, ready ? job?.request_id : null)

  useEffect(() => {
    if (open && !dialog.current?.open) dialog.current?.showModal()
    else if (!open && dialog.current?.open) dialog.current.close()
  }, [open])

  function dismiss() {
    setDismissed(visibilityKey)
    if (ready && job?.request_id) {
      try {
        localStorage.setItem(storageKey, job.request_id)
      } catch {
        /* Private browsing. */
      }
    }
  }

  return (
    <>
      {active && !open && !ready && (
        <button
          type="button"
          onClick={() => setDismissed("")}
          className="bg-card border-hair shadow-pop fixed right-5 bottom-5 z-40 flex items-center gap-2 rounded-full border px-4 py-2 text-sm"
        >
          <Monitor size={16} />
          {t("activation.viewProgress")}
        </button>
      )}
      <dialog
        ref={dialog}
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        onCancel={(event) => {
          event.preventDefault()
          dismiss()
        }}
        className="bg-card text-ink border-hair shadow-pop backdrop:bg-n900/40 fixed inset-0 m-auto w-110 max-w-[calc(100vw-2rem)] rounded-2xl border p-7"
      >
        <button
          type="button"
          onClick={dismiss}
          aria-label={t("activation.close")}
          className="text-n600 hover:bg-hairsoft absolute top-4 right-4 rounded-full p-1.5"
        >
          <X size={18} />
        </button>
        <div className="flex flex-col gap-5">
          <div className="bg-hairsoft flex size-12 items-center justify-center rounded-2xl">
            {ready ? <Check className="text-a700" size={24} /> : <Monitor className="text-a700" size={24} />}
          </div>
          <div>
            <h2 id={titleId} className="text-xl font-medium">
              {t(title)}
            </h2>
            <p className="text-n500 mt-1 truncate text-sm">{name}</p>
            <p id={bodyId} className="text-n600 mt-3 text-sm leading-relaxed">
              {t(ready ? "activation.readyHint" : "activation.hint")}
            </p>
          </div>
          <ol className="flex flex-col gap-4" aria-label={t("activation.progress")}>
            {steps.map((step, index) => {
              const complete = ready || index < position
              const current = !ready && index === position
              return (
                <li
                  key={step}
                  aria-current={current ? "step" : undefined}
                  className="flex items-center gap-3 text-sm"
                >
                  <span
                    className={cn(
                      "flex size-6 items-center justify-center rounded-full",
                      complete ? "bg-a700 text-bg" : "bg-hairsoft text-n500",
                    )}
                  >
                    {complete ? (
                      <Check size={14} />
                    ) : current && !attention ? (
                      <Spinner className="size-3.5" />
                    ) : (
                      index + 1
                    )}
                  </span>
                  <span className={cn(current ? "text-ink font-medium" : "text-n600")}>
                    {t(`activation.steps.${step}`)}
                  </span>
                </li>
              )
            })}
          </ol>
          <div aria-live="polite" className="text-n600 text-sm leading-relaxed">
            {query.isError ? t("activation.reconnecting") : message ? t(message) : null}
            {retry.isError && <p role="alert">{t("activation.retryFailed")}</p>}
          </div>
          <div className="flex justify-end gap-2">
            {job?.can_retry && canManage && (
              <button
                type="button"
                disabled={retry.isPending}
                onClick={() => retry.mutate()}
                className="border-hair rounded-full border px-4 py-2 text-sm disabled:opacity-50"
              >
                {t("activation.retry")}
              </button>
            )}
            <button type="button" onClick={dismiss} className="bg-ink text-bg rounded-full px-5 py-2 text-sm">
              {t(ready ? "activation.done" : "activation.continueChat")}
            </button>
          </div>
        </div>
      </dialog>
    </>
  )
}
