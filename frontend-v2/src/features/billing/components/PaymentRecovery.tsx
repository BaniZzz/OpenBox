import { ArrowUpRight, RefreshCw, X } from "lucide-react"
import { useTranslation } from "react-i18next"
import {
  useContinuePaymentOrder,
  useCancelPaymentOrder,
  useRefreshPaymentOrder,
  type PaymentOrder,
  type PaymentProvider,
} from "@/shared/api/billing"
import { useCheckoutRedirect } from "../hooks/useCheckoutRedirect"

export function PaymentRecovery({ order, provider }: { order: PaymentOrder; provider?: PaymentProvider }) {
  const { t } = useTranslation("billing")
  const refresh = useRefreshPaymentOrder()
  const checkout = useContinuePaymentOrder()
  const cancel = useCancelPaymentOrder()
  const redirect = useCheckoutRedirect()
  if (order.status !== "pending") return null
  const busy = refresh.isPending || checkout.isPending || cancel.isPending
  return (
    <div className="flex flex-col gap-3 text-sm">
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={busy}
          className="bg-ink text-bg flex min-h-11 items-center justify-center gap-2 rounded-full px-5 font-medium disabled:opacity-40"
          onClick={() => {
            void redirect(() => checkout.mutateAsync(order.id))
          }}
        >
          {t(checkout.isPending ? "usage.creatingOrder" : "usage.resumePayment")}
          <ArrowUpRight className="size-4" />
        </button>
        {provider?.supports_status_query && (
          <button
            type="button"
            disabled={busy}
            className="border-hair hover:bg-n200 flex min-h-11 items-center justify-center gap-2 rounded-full border px-5 disabled:opacity-40"
            onClick={() => refresh.mutate(order.id)}
          >
            <RefreshCw className="size-4" />
            {t(refresh.isPending ? "usage.queryingPayment" : "usage.queryPayment")}
          </button>
        )}
        {provider?.supports_cancel && (
          <button
            type="button"
            disabled={busy}
            className="border-hair hover:bg-n200 flex min-h-11 items-center justify-center gap-2 rounded-full border px-5 disabled:opacity-40"
            onClick={() => cancel.mutate(order.id)}
          >
            <X className="size-4" />
            {t(cancel.isPending ? "usage.cancellingPayment" : "usage.cancelPayment")}
          </button>
        )}
      </div>
      {cancel.isError && (
        <p role="alert" className="text-n600">
          {t("usage.cancelPaymentError")}
        </p>
      )}
      {refresh.isError && (
        <p role="alert" className="text-n600">
          {t("usage.queryPaymentError")}
        </p>
      )}
      {checkout.isError && (
        <p role="alert" className="text-n600">
          {t("usage.paymentError")}
        </p>
      )}
      {refresh.data?.status === "pending" && !busy && !refresh.isError && (
        <p role="status" className="text-n600">
          {t("usage.paymentNotConfirmed")}
        </p>
      )}
    </div>
  )
}
