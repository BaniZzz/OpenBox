import { useTranslation } from "react-i18next"
import { useEnvironmentQuery } from "@/shared/api/environment"

const STYLES: Record<string, { background: string; color: string }> = {
  dev: { background: "#FEF3C7", color: "#92400E" },
  staging: { background: "#DBEAFE", color: "#1E40AF" },
}

/** Small pill naming a non-production deployment; renders nothing for prod. */
export function EnvBadge() {
  const { t } = useTranslation("common")
  const environment = useEnvironmentQuery()
  const name = environment.data?.name ?? ""
  const style = STYLES[name]
  if (!style) return null
  return (
    <span
      data-testid="env-badge"
      title={t(`env.${name}Hint`)}
      className="flex-none select-none rounded-full px-2 py-0.5 text-xs font-medium"
      style={style}
    >
      {t(`env.${name}`)}
    </span>
  )
}
