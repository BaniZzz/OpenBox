// Publish one resource-centre video to Douyin. The backend signs an H5 share
// schema; this dialog turns it into a QR code the person scans with the Douyin
// app, then watches the job until the webhook reports the post.
import { useEffect, useMemo, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import QRCode from "qrcode"
import { CheckCircle2, Clock } from "lucide-react"
import { Dialog, DialogActions, DialogBody, DialogTitle } from "@/shared/ui/Dialog"
import { Spinner } from "@/shared/ui/Spinner"
import { ApiError } from "@/shared/api/http"
import { usePublishJob, usePublishToDouyin, usePublishableVideos } from "../api/platform-accounts"
import type { PublishResult } from "../types"

interface Props {
  open: boolean
  onClose: () => void
}

const MAX_BYTES = 128 * 1024 * 1024

function mb(size: number): string {
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function parseHashtags(raw: string): string[] {
  return raw
    .split(/[\s,，#]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 10)
}

function QrCanvas({ text, label }: { text: string; label: string }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    if (!ref.current) return
    void QRCode.toCanvas(ref.current, text, { width: 240, margin: 1, errorCorrectionLevel: "M" })
  }, [text])
  return <canvas ref={ref} className="rounded-lg bg-white" aria-label={label} />
}

function Countdown({ until }: { until: string | null }) {
  const { t } = useTranslation("auth-center")
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])
  if (!until) return null
  const left = Math.max(0, Math.floor((new Date(until).getTime() - now) / 1000))
  const m = Math.floor(left / 60)
  const s = left % 60
  return (
    <span className="text-n600 flex items-center gap-1 text-xs">
      <Clock size={12} />
      {t("publish.expiresIn", { time: `${m}:${s.toString().padStart(2, "0")}` })}
    </span>
  )
}

export function PublishDialog({ open, onClose }: Props) {
  const { t } = useTranslation("auth-center")
  const [assetId, setAssetId] = useState("")
  const [title, setTitle] = useState("")
  const [tags, setTags] = useState("")
  const [privacy, setPrivacy] = useState<0 | 1 | 2>(0)
  const [result, setResult] = useState<PublishResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const videos = usePublishableVideos(open)
  const publish = usePublishToDouyin()
  const job = usePublishJob(result?.job.id ?? null, open && !!result)

  const eligible = useMemo(
    () => (videos.data ?? []).filter((v) => v.size <= MAX_BYTES && /video\/(mp4|quicktime|3gpp)/.test(v.mime)),
    [videos.data],
  )

  const submit = () => {
    setError(null)
    publish.mutate(
      { fileAssetId: assetId, title: title.trim(), hashtags: parseHashtags(tags), privateStatus: privacy },
      {
        onSuccess: setResult,
        onError: (e) => {
          const code = e instanceof ApiError ? e.code : "PLATFORM_ERROR"
          setError(t(`errors.${code}`, { defaultValue: e instanceof Error ? e.message : String(e) }))
        },
      },
    )
  }

  const status = job.data?.status ?? result?.job.status ?? "pending"

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>{t("publish.title")}</DialogTitle>

      {!result ? (
        <>
          <DialogBody>{t("publish.intro")}</DialogBody>
          <label className="mt-2 flex flex-col gap-1 text-sm">
            <span className="text-n700">{t("publish.video")}</span>
            {videos.isLoading ? (
              <Spinner />
            ) : videos.isError ? (
              <span className="text-danger text-xs">{t("publish.videosError")}</span>
            ) : (
              <select
                value={assetId}
                onChange={(e) => setAssetId(e.target.value)}
                className="border-hair bg-bg text-ink rounded-lg border px-2.5 py-2 text-sm"
              >
                <option value="">{eligible.length ? t("publish.pickVideo") : t("publish.noVideos")}</option>
                {eligible.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} · {mb(v.size)}
                  </option>
                ))}
              </select>
            )}
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-n700">{t("publish.caption")}</span>
            <input
              value={title}
              maxLength={55}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t("publish.captionPlaceholder")}
              className="border-hair bg-bg text-ink rounded-lg border px-2.5 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-n700">{t("publish.hashtags")}</span>
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder={t("publish.hashtagsPlaceholder")}
              className="border-hair bg-bg text-ink rounded-lg border px-2.5 py-2 text-sm"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-n700">{t("publish.privacy")}</span>
            <select
              value={privacy}
              onChange={(e) => setPrivacy(Number(e.target.value) as 0 | 1 | 2)}
              className="border-hair bg-bg text-ink rounded-lg border px-2.5 py-2 text-sm"
            >
              <option value={0}>{t("publish.privacyPublic")}</option>
              <option value={2}>{t("publish.privacyFriends")}</option>
              <option value={1}>{t("publish.privacyPrivate")}</option>
            </select>
          </label>
          {error ? <span className="text-danger text-sm">{error}</span> : null}
          <DialogActions>
            <button type="button" className="text-md text-n700" onClick={onClose}>
              {t("common:action.cancel", { ns: "common" })}
            </button>
            <button
              type="button"
              disabled={!assetId || publish.isPending}
              onClick={submit}
              className="bg-ink text-bg text-md flex items-center gap-2 rounded-full px-4.5 py-2 font-medium disabled:opacity-50"
            >
              {publish.isPending ? <Spinner className="border-t-bg" /> : null}
              {t("publish.generate")}
            </button>
          </DialogActions>
        </>
      ) : (
        <>
          {status === "published" ? (
            <div className="flex flex-col items-center gap-2 py-4 text-center">
              <CheckCircle2 size={40} className="text-a700" />
              <span className="text-ink text-base font-medium">{t("publish.done")}</span>
              {job.data?.itemId ? (
                <span className="text-n600 text-xs">{t("publish.itemId", { id: job.data.itemId })}</span>
              ) : null}
            </div>
          ) : status === "expired" ? (
            <div className="flex flex-col items-center gap-2 py-4 text-center">
              <span className="text-ink text-base font-medium">{t("publish.expired")}</span>
              <span className="text-n600 text-xs">{t("publish.expiredHint")}</span>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3 py-2 text-center">
              <QrCanvas text={result.schema} label={t("publish.qrAlt")} />
              <span className="text-ink text-sm">{t("publish.scanHint")}</span>
              <span className="text-n600 text-xs">{t("publish.scanSteps")}</span>
              <div className="flex items-center gap-3">
                <Spinner />
                <span className="text-n600 text-xs">{t("publish.waiting")}</span>
                <Countdown until={result.job.expiresAt} />
              </div>
              {!result.job.shareId ? (
                <span className="text-n600 text-xs">{t("publish.noTracking")}</span>
              ) : null}
            </div>
          )}
          <DialogActions>
            <button type="button" className="text-md text-n700" onClick={onClose}>
              {t("common:action.close", { ns: "common" })}
            </button>
          </DialogActions>
        </>
      )}
    </Dialog>
  )
}
