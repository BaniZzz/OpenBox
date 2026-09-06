import { useState } from "react"
import { useTranslation } from "react-i18next"
import {
  usePaymentOrders,
  usePaymentProviders,
  usePaymentStatusSync,
  type PaymentOrderFilters,
} from "@/shared/api/billing"
import { formatCredits, formatDateTime, formatNumber } from "@/shared/lib/format"
import { Spinner } from "@/shared/ui/Spinner"
import { PaymentRecovery } from "./PaymentRecovery"
import { OrderFilters } from "./OrderFilters"

export function PaymentHistory() {
  const { t } = useTranslation("billing")
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<PaymentOrderFilters>({})
  const [pageSize, setPageSize] = useState(10)
  const providers = usePaymentProviders()
  const orders = usePaymentOrders(page, filters, pageSize)
  const sync = usePaymentStatusSync(orders.data?.items, providers.data?.items)
  const pages = orders.data?.total_pages ?? 1
  // Payment/cancellation can remove the last row of a filtered final page.
  if (orders.data?.page === page && page > pages) setPage(pages)
  return (
    <section className="flex min-w-0 flex-col gap-5" aria-label={t("usage.paymentHistory")}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-medium">{t("usage.paymentHistory")}</h1>
        <span className="text-n600 text-sm" aria-live="polite">
          {t("orders.count", { count: orders.data?.total ?? 0 })}
        </span>
      </div>
      <OrderFilters
        providers={providers.data?.items ?? []}
        onChange={(next) => {
          setFilters(next)
          setPage(1)
        }}
      />
      {sync.data?.failed && (
        <p role="status" className="text-n600 text-sm">
          {t("usage.paymentStatusError")}
        </p>
      )}
      {orders.isError && (
        <div role="alert" className="flex items-center justify-between gap-2 text-sm">
          <span>{t("usage.paymentHistoryError")}</span>
          <button type="button" className="underline" onClick={() => void orders.refetch()}>
            {t("usage.retry")}
          </button>
        </div>
      )}
      {orders.isLoading ? (
        <Spinner className="size-5 self-center" />
      ) : orders.data?.items.length ? (
        <ul className="flex min-w-0 flex-col gap-3">
          {orders.data.items.map((order) => (
            <li
              key={order.id}
              className="border-hair bg-card flex min-w-0 flex-col gap-4 rounded-xl border p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex flex-col gap-1.5">
                  <h2 className="font-medium">
                    {order.kind === "subscription"
                      ? t("plans.orderTitle", {
                          name: t("plans.names." + order.plan_id),
                          cycle: t("plans.cycles." + order.cycle),
                        })
                      : t("plans.extraCredits")}
                  </h2>
                  <span className="text-n600 text-sm">
                    {order.kind === "subscription"
                      ? t("plans.allowance.monthly", { credits: formatCredits(order.credits) })
                      : t("usage.points", { value: formatCredits(order.credits) })}
                  </span>
                </div>
                <span className="bg-n200 rounded-full px-3 py-1.5 text-sm" role="status">
                  {t("usage.paymentState." + order.status)}
                </span>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-2xl font-medium tabular-nums">
                  ¥{formatNumber(order.amount_fen / 100)}
                </span>
                <span className="text-n600 text-sm">
                  {providers.data?.items.find((item) => item.id === order.provider)?.name ?? order.provider}
                </span>
              </div>
              <div className="text-n600 flex flex-col gap-1.5 text-xs">
                <span className="break-all">{t("usage.orderNumber", { id: order.id })}</span>
                <span>
                  {t("orders.createdAt")}{" "}
                  <time dateTime={order.created_at}>{formatDateTime(order.created_at)}</time>
                </span>
                {order.paid_at && (
                  <span>
                    {t("orders.paidAt")} <time dateTime={order.paid_at}>{formatDateTime(order.paid_at)}</time>
                  </span>
                )}
                {order.cancelled_at && order.status === "cancelled" && (
                  <span>
                    {t("orders.cancelledAt")}{" "}
                    <time dateTime={order.cancelled_at}>{formatDateTime(order.cancelled_at)}</time>
                  </span>
                )}
              </div>
              {order.reconcile_required && <p className="text-n600 text-sm">{t("orders.closeOldCashier")}</p>}
              <PaymentRecovery
                order={order}
                provider={providers.data?.items.find((item) => item.id === order.provider)}
              />
            </li>
          ))}
        </ul>
      ) : (
        !orders.isError && (
          <p className="border-hair text-n600 rounded-xl border py-12 text-center text-sm">
            {t("usage.noPayments")}
          </p>
        )
      )}
      <nav
        className="text-n600 flex flex-wrap items-center justify-between gap-3 text-sm"
        aria-label={t("usage.paymentPagination")}
      >
        <label className="flex items-center gap-2">
          {t("usage.pageSize")}
          <select
            value={pageSize}
            onChange={(event) => {
              setPageSize(Number(event.target.value))
              setPage(1)
            }}
            className="border-hair bg-card text-ink min-h-10 rounded-full border px-3"
          >
            {[10, 20, 50].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-center gap-3">
          <button
            type="button"
            disabled={page <= 1 || orders.isFetching}
            onClick={() => setPage(page - 1)}
            className="border-hair min-h-10 rounded-full border px-4 disabled:opacity-40"
          >
            {t("usage.previous")}
          </button>
          <span aria-live="polite">{t("usage.page", { page, pages })}</span>
          <button
            type="button"
            disabled={page >= pages || orders.isFetching}
            onClick={() => setPage(page + 1)}
            className="border-hair min-h-10 rounded-full border px-4 disabled:opacity-40"
          >
            {t("usage.next")}
          </button>
        </div>
      </nav>
    </section>
  )
}
