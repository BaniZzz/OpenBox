import { useState } from "react"
import { useTranslation } from "react-i18next"
import type { PaymentOrderFilters, PaymentProvider } from "@/shared/api/billing"
import { cn } from "@/shared/lib/cn"

const STATUSES = ["all", "pending", "paid", "cancelled"] as const

export function OrderFilters({
  providers,
  onChange,
}: {
  providers: PaymentProvider[]
  onChange: (filters: PaymentOrderFilters) => void
}) {
  const { t } = useTranslation("billing")
  const [draft, setDraft] = useState<PaymentOrderFilters>({})
  const invalid = Boolean(draft.date_from && draft.date_to && draft.date_from > draft.date_to)
  const apply = (filters: PaymentOrderFilters) => {
    if (filters.date_from && filters.date_to && filters.date_from > filters.date_to) return
    onChange({
      ...filters,
      order_id: filters.order_id?.trim(),
      tz: filters.date_from || filters.date_to ? Intl.DateTimeFormat().resolvedOptions().timeZone : undefined,
    })
  }
  return (
    <form
      className="border-hair bg-card flex min-w-0 flex-col gap-4 rounded-xl border p-4"
      aria-label={t("orders.filters")}
      onSubmit={(event) => {
        event.preventDefault()
        apply(draft)
      }}
    >
      <div className="flex flex-wrap gap-2" role="group" aria-label={t("orders.status")}>
        {STATUSES.map((status) => (
          <button
            key={status}
            type="button"
            aria-pressed={(draft.status ?? "all") === status}
            className={cn(
              "min-h-10 rounded-full px-4 text-sm",
              (draft.status ?? "all") === status ? "bg-ink text-bg" : "bg-n200 text-ink hover:bg-n300",
            )}
            onClick={() => {
              const next = { ...draft, status: status === "all" ? undefined : status }
              setDraft(next)
              apply(next)
            }}
          >
            {status === "all" ? t("orders.all") : t("usage.paymentState." + status)}
          </button>
        ))}
      </div>
      <div className="grid min-w-0 grid-cols-1 gap-3 @min-[440px]/billing:grid-cols-2">
        <label className="text-n600 flex min-w-0 flex-col gap-1.5 text-sm">
          {t("orders.orderId")}
          <input
            type="search"
            maxLength={64}
            placeholder={t("orders.orderIdPlaceholder")}
            value={draft.order_id ?? ""}
            onChange={(event) => setDraft({ ...draft, order_id: event.target.value })}
            className="border-hair bg-bg text-ink min-h-11 min-w-0 rounded-lg border px-3"
          />
        </label>
        <label className="text-n600 flex min-w-0 flex-col gap-1.5 text-sm">
          {t("usage.paymentChannel")}
          <select
            value={draft.provider ?? ""}
            onChange={(event) => setDraft({ ...draft, provider: event.target.value })}
            className="border-hair bg-bg text-ink min-h-11 min-w-0 rounded-lg border px-3"
          >
            <option value="">{t("orders.allChannels")}</option>
            {providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-n600 flex min-w-0 flex-col gap-1.5 text-sm">
          {t("usage.dateFrom")}
          <input
            type="date"
            value={draft.date_from ?? ""}
            max={draft.date_to || undefined}
            onChange={(event) => setDraft({ ...draft, date_from: event.target.value })}
            className="border-hair bg-bg text-ink min-h-11 w-full min-w-0 rounded-lg border px-3"
          />
        </label>
        <label className="text-n600 flex min-w-0 flex-col gap-1.5 text-sm">
          {t("usage.dateTo")}
          <input
            type="date"
            value={draft.date_to ?? ""}
            min={draft.date_from || undefined}
            onChange={(event) => setDraft({ ...draft, date_to: event.target.value })}
            className="border-hair bg-bg text-ink min-h-11 w-full min-w-0 rounded-lg border px-3"
          />
        </label>
      </div>
      {invalid && (
        <p role="alert" className="text-n600 text-sm">
          {t("usage.invalidDates")}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="submit"
          disabled={invalid}
          className="bg-ink text-bg min-h-10 rounded-full px-5 text-sm disabled:opacity-40"
        >
          {t("usage.applyFilter")}
        </button>
        <button
          type="button"
          onClick={() => {
            setDraft({})
            onChange({})
          }}
          className="border-hair hover:bg-n200 min-h-10 rounded-full border px-5 text-sm"
        >
          {t("usage.resetFilter")}
        </button>
      </div>
    </form>
  )
}
