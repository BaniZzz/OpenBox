import { CreditCard, Check } from "lucide-react"
import { useTranslation } from "react-i18next"
import type { PaymentProvider } from "@/shared/api/billing"
import { cn } from "@/shared/lib/cn"

export function PaymentChannelPicker({
  providers,
  value,
  onChange,
}: {
  providers: PaymentProvider[]
  value: string
  onChange: (value: string) => void
}) {
  const { t } = useTranslation("billing")
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label={t("usage.paymentChannel")}>
      <span className="text-n600 text-sm">{t("usage.paymentChannel")}</span>
      {providers.map((provider) => (
        <button
          type="button"
          key={provider.id}
          aria-pressed={provider.id === value}
          onClick={() => onChange(provider.id)}
          className={cn(
            "flex min-h-11 items-center gap-2 rounded-full border px-4 text-sm font-medium",
            provider.id === value
              ? "border-ink bg-ink text-bg"
              : "border-hair bg-card text-ink hover:bg-n200",
          )}
        >
          <CreditCard className="size-4" />
          {provider.name}
          {provider.id === value && <Check className="size-4" />}
        </button>
      ))}
    </div>
  )
}
