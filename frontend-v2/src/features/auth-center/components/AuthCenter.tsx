// 授权中心 — which platform accounts this workspace can act as.
//
// Binding leaves the app: the backend hands back the platform's authorize URL,
// the person scans there, and the platform redirects to the backend callback,
// which lands them back here with `?bound=` or `?error=` in the URL.
import { useEffect, useMemo, useState } from "react"
import { useTranslation } from "react-i18next"
import { useSearchParams } from "react-router"
import { Dialog, DialogActions, DialogBody, DialogTitle } from "@/shared/ui/Dialog"
import { Spinner } from "@/shared/ui/Spinner"
import { toast } from "@/shared/ui/Toast"
import { ApiError } from "@/shared/api/http"
import {
  useCanManageAccounts,
  usePlatformAccounts,
  usePlatforms,
  useProbeAccount,
  useStartAuthorize,
  useUnbindAccount,
} from "../api/platform-accounts"
import type { PlatformAccount } from "../types"
import { PlatformCard } from "./PlatformCard"
import { PublishDialog } from "./PublishDialog"

function errorCode(e: unknown): string {
  return e instanceof ApiError ? e.code : "PLATFORM_ERROR"
}

export function AuthCenter() {
  const { t } = useTranslation("auth-center")
  const [params, setParams] = useSearchParams()
  const platforms = usePlatforms()
  const accounts = usePlatformAccounts()
  const canManage = useCanManageAccounts()
  const startAuthorize = useStartAuthorize()
  const probe = useProbeAccount()
  const unbind = useUnbindAccount()
  const [pendingUnbind, setPendingUnbind] = useState<PlatformAccount | null>(null)
  const [publishFor, setPublishFor] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  // The OAuth round trip reports back through the URL; read it once, say
  // what happened, and clean the address bar so a reload does not repeat it.
  useEffect(() => {
    const bound = params.get("bound")
    const error = params.get("error")
    if (!bound && !error) return
    if (bound) toast.success(t("toast.bound"))
    if (error) toast.error(t(`errors.${error}`, { defaultValue: t("errors.PLATFORM_ERROR") }))
    const next = new URLSearchParams(params)
    next.delete("bound")
    next.delete("error")
    next.delete("platform")
    setParams(next, { replace: true })
  }, [params, setParams, t])

  const byPlatform = useMemo(() => {
    const map = new Map<string, PlatformAccount[]>()
    for (const a of accounts.data ?? []) {
      const list = map.get(a.platform) ?? []
      list.push(a)
      map.set(a.platform, list)
    }
    return map
  }, [accounts.data])

  const onBind = (platform: string) => {
    startAuthorize.mutate(platform, {
      onError: (e) => toast.error(t(`errors.${errorCode(e)}`, { defaultValue: t("errors.PLATFORM_ERROR") })),
    })
  }

  const onProbe = (id: string) => {
    setBusyId(id)
    probe.mutate(id, {
      onSuccess: (row) => {
        if (row.status === "bound") toast.success(t("toast.probeOk"))
        else toast.warning(t("toast.probeExpired"))
      },
      onError: (e) => toast.error(t(`errors.${errorCode(e)}`, { defaultValue: t("errors.PLATFORM_ERROR") })),
      onSettled: () => setBusyId(null),
    })
  }

  const confirmUnbind = () => {
    const target = pendingUnbind
    if (!target) return
    setPendingUnbind(null)
    setBusyId(target.id)
    unbind.mutate(target.id, {
      onSuccess: () => toast.success(t("toast.unbound")),
      onError: (e) => toast.error(t(`errors.${errorCode(e)}`, { defaultValue: t("errors.PLATFORM_ERROR") })),
      onSettled: () => setBusyId(null),
    })
  }

  if (platforms.isLoading || accounts.isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    )
  }
  if (platforms.isError || accounts.isError) {
    return (
      <div className="border-hair text-danger rounded-xl border px-4 py-6 text-center text-sm">
        {t("state.error")}
        <button
          type="button"
          className="text-ink ms-3 underline"
          onClick={() => {
            void platforms.refetch()
            void accounts.refetch()
          }}
        >
          {t("common:action.retry", { ns: "common" })}
        </button>
      </div>
    )
  }
  const list = platforms.data ?? []
  if (list.length === 0) {
    return (
      <div className="border-hair text-n600 rounded-xl border border-dashed px-4 py-10 text-center text-sm">
        {t("state.noPlatforms")}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {list.map((platform) => (
        <PlatformCard
          key={platform.key}
          platform={platform}
          accounts={byPlatform.get(platform.key) ?? []}
          canManage={canManage}
          busyId={busyId}
          binding={startAuthorize.isPending}
          onBind={onBind}
          onProbe={onProbe}
          onUnbind={setPendingUnbind}
          onPublish={setPublishFor}
        />
      ))}

      <Dialog open={pendingUnbind !== null} onClose={() => setPendingUnbind(null)}>
        <DialogTitle>{t("unbind.title")}</DialogTitle>
        <DialogBody>
          {t("unbind.body", { name: pendingUnbind?.nickname || pendingUnbind?.externalId || "" })}
        </DialogBody>
        <DialogActions>
          <button type="button" className="text-md text-n700" onClick={() => setPendingUnbind(null)}>
            {t("common:action.cancel", { ns: "common" })}
          </button>
          <button
            type="button"
            className="bg-danger text-md text-bg rounded-full px-4.5 py-2 font-medium"
            onClick={confirmUnbind}
          >
            {t("actions.unbind")}
          </button>
        </DialogActions>
      </Dialog>

      {/* Keyed on the platform so closing and reopening starts from a blank form. */}
      <PublishDialog
        key={publishFor ?? "closed"}
        open={publishFor === "douyin"}
        onClose={() => setPublishFor(null)}
      />
    </div>
  )
}
