export interface FleetDesktop {
  id: string
  desktop_id?: string | null
  ecd_end_user_ids?: string[] | null
  ecd_end_users?: Array<{ id: string; username?: string | null }> | null
  workspace_id?: string | null
  pool_state: string
  status: string
  tunnel_state: string
  charge_type?: string | null
  expires_at?: string | null
  spec?: string | null
  golden_image_id?: string | null
}

export interface FleetAlert {
  id: string
  rule: string
  severity: "info" | "warn" | "critical"
  resource_id: string
  message: string
  first_seen_at: string
  last_seen_at: string
  acked_at?: string | null
  muted_until?: string | null
}

export interface PoolSummary {
  states: Record<string, number>
  target_prewarm: number
  purchased_today: number
  enabled: boolean
  auto_purchase: boolean
  auto_renew: boolean
  gates: {
    max_unit_price_cny: number
    max_per_tick: number
    max_per_day: number
    min_balance_multiple: number
  }
}

export interface PoolEnsureResult {
  status: "disabled" | "satisfied" | "blocked" | "dry_run" | "purchased"
  current: number
  target: number
  gap: number
  quantity: number
  unit_price?: number
  currency?: string
  gate?: string
  message?: string
  created?: string[]
}

export interface FleetSnapshot {
  taken_at?: string | null
  sources: Array<{ source: string; ok: boolean; error?: string | null }>
}
