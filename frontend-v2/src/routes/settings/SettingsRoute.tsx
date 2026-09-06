import { useTranslation } from "react-i18next"
import { Navigate, useParams } from "react-router"
import { paths } from "@/shared/router/paths"
import {
  SettingsNav,
  SETTINGS_TABS,
  type SettingsTab,
  AccountPage,
  ModelsPage,
  BrowserPage,
  AppearancePage,
  TeamPage,
} from "@/features/settings"

function ActivePage({ tab }: { tab: SettingsTab }) {
  switch (tab) {
    case "team":
      return <TeamPage />
    case "models":
      return <ModelsPage />
    case "browser":
      return <BrowserPage />
    case "appearance":
      return <AppearancePage />
    default:
      return <AccountPage />
  }
}

export default function SettingsRoute() {
  const { t } = useTranslation("settings")
  const { tab } = useParams()
  if (tab === "usage") return <Navigate to={paths.billing("usage")} replace />
  const active: SettingsTab = SETTINGS_TABS.includes(tab as SettingsTab) ? (tab as SettingsTab) : "account"

  return (
    <div className="scr @container/settings min-h-0 flex-1 overflow-auto px-4 pt-1.5 pb-7">
      <div className="mx-auto flex w-full max-w-[860px] flex-col items-stretch gap-5 @min-[640px]/settings:flex-row @min-[640px]/settings:items-start @min-[640px]/settings:gap-7">
        <SettingsNav active={active} />
        <div className="flex min-w-0 flex-1 flex-col gap-4.5">
          <div className="flex flex-col gap-1">
            <span className="text-2xl font-medium tracking-tight">{t(`nav.${active}`)}</span>
            <span className="text-n600 text-sm">{t(`hint.${active}`)}</span>
          </div>
          <ActivePage tab={active} />
        </div>
      </div>
    </div>
  )
}
