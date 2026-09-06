import { env } from "@/shared/config/env"

export interface LogtoConfig {
  enabled: boolean
  endpoint: string
  issuer: string
  app_id: string
  redirect_uri: string
  post_logout_redirect_uri: string
}

/** Public OIDC settings; null means Logto is disabled or unreachable. */
export async function getLogtoConfig(): Promise<LogtoConfig | null> {
  try {
    const resp = await fetch(`${env.apiBase}/api/auth/logto/config`)
    if (!resp.ok) return null
    const data = (await resp.json()) as LogtoConfig
    return data.enabled ? data : null
  } catch {
    return null
  }
}
