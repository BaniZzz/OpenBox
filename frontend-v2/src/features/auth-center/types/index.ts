// 授权中心 contracts — mirrors backend/platforms/service.py `to_public`.

export type PlatformCapability = "login" | "publish"

export interface Platform {
  key: string
  display: string
  capabilities: PlatformCapability[]
  /** False when the deployment has no client key for it; the card is shown greyed. */
  configured: boolean
  maxGrantDays: number | null
}

export type AccountStatus = "bound" | "expired" | "revoked"

export interface PlatformAccount {
  id: string
  platform: string
  authKind: "oauth" | "desktop_cookie"
  externalId: string
  unionId: string | null
  nickname: string | null
  avatarUrl: string | null
  scopes: string[]
  status: AccountStatus
  accessExpiresAt: string | null
  refreshExpiresAt: string | null
  renewCount: number
  renewalsLeft: number
  lastRefreshAt: string | null
  lastProbeAt: string | null
  lastOkAt: string | null
  lastError: string | null
  boundAt: string | null
  boundByUserId: string
}

export type PublishStatus = "pending" | "published" | "failed" | "expired"

export interface PublishJob {
  id: string
  platform: string
  platformAccountId: string | null
  fileAssetId: string
  title: string
  hashtags: string[]
  shareId: string | null
  status: PublishStatus
  itemId: string | null
  videoId: string | null
  fromOpenId: string | null
  error: string | null
  expiresAt: string | null
  publishedAt: string | null
  createdAt: string | null
}

export interface PublishResult {
  job: PublishJob
  /** The snssdk1128:// share schema; rendered as a QR code, never persisted. */
  schema: string
}

/** Subset of the resource-centre item this feature needs to pick a video. */
export interface VideoAsset {
  id: string
  name: string
  mime: string
  size: number
  kind: string
  createdAt: string
}
