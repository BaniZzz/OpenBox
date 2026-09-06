import { useTranslation } from "react-i18next"
import { useBillingPlans, useBillingSubscription, useCreditBalance } from "@/shared/api/billing"
import { formatDateTime } from "@/shared/lib/format"
import { Spinner } from "@/shared/ui/Spinner"
import { CreditBalanceCard } from "./CreditBalanceCard"
import { CreditTopUp } from "./CreditTopUp"
import { PlanOptions } from "./PlanOptions"

export function PurchasePage() {
  const { t } = useTranslation("billing")
  const balance = useCreditBalance()
  const catalog = useBillingPlans()
  const subscription = useBillingSubscription()
  return (
    <div className="flex min-w-0 flex-col gap-5">
      <CreditBalanceCard balance={balance.data?.balance}>
        {subscription.data && (
          <div className="border-hair text-n600 flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-xs">
            <span>{t("plans.activePlan", { name: t(`plans.names.${subscription.data.plan_id}`) })}</span>
            {subscription.data.ends_at && (
              <span>{t("plans.expires", { date: formatDateTime(subscription.data.ends_at) })}</span>
            )}
          </div>
        )}
      </CreditBalanceCard>
      {(balance.isError || catalog.isError || subscription.isError) && (
        <div role="alert" className="flex items-center justify-between gap-2 text-sm">
          <span>{t("usage.loadError")}</span>
          <button
            type="button"
            className="underline"
            onClick={() => {
              void balance.refetch()
              void catalog.refetch()
              void subscription.refetch()
            }}
          >
            {t("usage.retry")}
          </button>
        </div>
      )}
      {(catalog.isLoading || subscription.isLoading) && <Spinner className="size-5 self-center" />}
      {catalog.data && subscription.data && (
        <>
          <PlanOptions catalog={catalog.data} subscription={subscription.data} />
          {subscription.data.queued.length > 0 && (
            <section
              className="border-hair bg-card flex flex-col gap-2 rounded-xl border p-5"
              aria-label={t("plans.queued")}
            >
              <h2 className="text-sm font-medium">{t("plans.queued")}</h2>
              {subscription.data.queued.map((term) => (
                <p key={term.starts_at} className="text-n600 text-xs">
                  {t("plans.scheduled", {
                    name: t(`plans.names.${term.plan_id}`),
                    date: formatDateTime(term.starts_at!),
                  })}
                </p>
              ))}
            </section>
          )}
          <section
            className="border-hair bg-card flex min-w-0 flex-col gap-4 rounded-xl border p-5"
            aria-label={t("plans.extraCredits")}
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-base font-medium">{t("plans.extraCredits")}</h2>
              <span className="text-n600 text-xs">{t("plans.topupRate")}</span>
            </div>
            <CreditTopUp
              rules={catalog.data.topup}
              allowed={subscription.data.topup_allowed}
              canManage={subscription.data.can_manage}
            />
          </section>
          <details className="border-hair text-n600 rounded-xl border px-5 py-4 text-xs">
            <summary className="text-ink cursor-pointer font-medium">{t("plans.rulesTitle")}</summary>
            <ul className="mt-3 flex list-disc flex-col gap-2 ps-4 leading-relaxed">
              <li>{t("plans.rules.periods")}</li>
              <li>{t("plans.rules.yearly")}</li>
              <li>{t("plans.rules.balance")}</li>
              <li>{t("plans.rules.renewal")}</li>
              <li>
                {t("plans.rules.topup", {
                  min: catalog.data.topup.min_amount_fen / 100,
                  max: catalog.data.topup.max_amount_fen / 100,
                })}
              </li>
            </ul>
          </details>
        </>
      )}
    </div>
  )
}
