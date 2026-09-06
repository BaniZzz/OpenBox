import { Link, useParams } from "react-router"
import { useTranslation } from "react-i18next"
import { UsagePage, PurchasePage, PaymentHistory, CheckoutRedirectProvider } from "@/features/billing"
import { useWorkspaceStore } from "@/shared/api/workspace-store"
import { useAuthStore } from "@/shared/api/auth-store"
import { paths } from "@/shared/router/paths"
import { cn } from "@/shared/lib/cn"

const TABS = ["purchase", "usage", "orders"] as const

export default function BillingRoute() {
  const { t } = useTranslation("billing")
  const { tab } = useParams()
  const active = TABS.find((value) => value === tab) ?? "purchase"
  const workspaceId = useWorkspaceStore((state) => state.currentId)
  const userId = useAuthStore((state) => state.user?.id)
  return (
    <CheckoutRedirectProvider key={`${userId}:${workspaceId}`}>
      <div className="scr @container/billing min-h-0 flex-1 overflow-auto px-4 pt-1.5 pb-7">
        <div className="mx-auto flex w-full max-w-[860px] flex-col gap-5">
          <nav className="flex flex-wrap gap-1" aria-label={t("title")}>
            {TABS.map((value) => (
              <Link
                key={value}
                to={paths.billing(value)}
                aria-current={active === value ? "page" : undefined}
                className={cn(
                  "rounded-full px-4 py-2 text-sm",
                  active === value ? "bg-n300 text-ink font-medium" : "text-n700 hover:bg-n200",
                )}
              >
                {t(`tabs.${value}`)}
              </Link>
            ))}
          </nav>
          <div key={`${userId}:${workspaceId}:${active}`}>
            {active === "usage" ? <UsagePage /> : active === "orders" ? <PaymentHistory /> : <PurchasePage />}
          </div>
        </div>
      </div>
    </CheckoutRedirectProvider>
  )
}
