import type { ReactNode } from "react"
import { useTranslation } from "react-i18next"
import { Coins } from "lucide-react"
import { formatCredits } from "@/shared/lib/format"

export function CreditBalanceCard({ balance, children }: { balance?: string; children?: ReactNode }) {
  const { t } = useTranslation("billing")
  return (
    <section
      className="border-hair bg-card flex flex-col gap-4 rounded-xl border p-5"
      aria-label={t("usage.balance")}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="text-n600 flex items-center gap-1.5 text-sm">
          <Coins className="size-4" />
          {t("usage.balance")}
        </span>
        <span className="text-2xl font-medium whitespace-nowrap tabular-nums">
          {t("usage.points", { value: formatCredits(balance) })}
        </span>
      </div>
      {children}
    </section>
  )
}
