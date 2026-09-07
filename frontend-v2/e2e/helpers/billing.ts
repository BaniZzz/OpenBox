import type { Page, Route } from "@playwright/test"
import planCatalog from "../../../backend/billing/plans.json" with { type: "json" }

export async function billingApi(page: Page, initialPlan = "pro", alipayTest = false) {
  const catalog = structuredClone(planCatalog)
  let paid = false
  let checkoutReady = false
  let newOrders = 0
  const resumed: string[] = []
  const submitted: Record<string, unknown>[] = []
  let planOrder: Record<string, unknown> | null = null
  let planPaid = false
  let planCancelled = false
  let cancelError = false
  let confirmOnQuery = false
  let queryError = false
  const queries: string[] = []
  const planOrderView = () =>
    planOrder && {
      ...planOrder,
      status: planPaid ? "paid" : planCancelled ? "cancelled" : "pending",
      starts_at: planPaid ? "2026-09-05T01:00:00Z" : null,
      ends_at: planPaid ? "2027-09-05T01:00:00Z" : null,
    }
  const usageRequests: URL[] = []
  const summaryRequests: URL[] = []
  async function queryPlanOrder(route: Route) {
    queries.push(route.request().headers()["x-workspace-id"])
    if (queryError) {
      await route.fulfill({ status: 502, json: { detail: { code: "PAYMENT_QUERY_FAILED" } } })
      return
    }
    if (confirmOnQuery) planPaid = true
    await route.fulfill({ json: planOrderView() })
  }
  const records = Array.from({ length: 21 }, (_, n) => ({
    id: `usage-${n + 1}`,
    session_id: `session-${n + 1}`,
    session_title: `测试会话 ${n + 1}`,
    session_available: true,
    model_id: n % 2 ? "openai/qwen3.8-max" : "openai/gpt-5.6-luna",
    kind: "chat",
    tokens: { input: 12500, output: 2500, cache: 6000 },
    total_tokens: 15000,
    credits: "0.00412",
    status: "charged",
    // The final record is just before local midnight on September 4.
    created_at: n === 20 ? "2026-09-04T15:59:00Z" : "2026-09-05T01:00:00Z",
    pricing_version: "2026-09-05.2",
  }))
  function selectedRecords(url: URL) {
    const from = url.searchParams.get("date_from")
    const to = url.searchParams.get("date_to")
    return records.filter((entry) => {
      const localDate = new Date(Date.parse(entry.created_at) + 8 * 3600000).toISOString().slice(0, 10)
      return (!from || localDate >= from) && (!to || localDate <= to)
    })
  }
  const order = () => ({
    id: "pay-existing",
    kind: "topup",
    amount_fen: 1000,
    provider: "gateway",
    credits: "10",
    status: paid ? "paid" : "pending",
    checkout_url: checkoutReady ? "https://checkout.example.test/existing" : null,
    created_at: "2026-09-05T01:00:00Z",
    paid_at: paid ? "2026-09-05T02:00:00Z" : null,
  })
  const balanceView = () => ({
    workspace_id: "ws-fixture",
    balance: String(
      (initialPlan === "free" ? 10 : 88.125) + (paid ? 10 : 0) + (planPaid ? Number(planOrder?.credits) : 0),
    ),
    mode: "enforce",
  })
  const subscriptionView = () => {
    const planId = planPaid ? String(planOrder?.plan_id) : initialPlan
    const plan = catalog.plans.find((item) => item.id === planId)!
    return {
      plan_id: planId,
      cycle: planId === "free" ? null : "yearly",
      starts_at: planId === "free" ? null : "2026-09-05T01:00:00Z",
      ends_at: planId === "free" ? null : "2027-09-05T01:00:00Z",
      credits: plan.credits,
      credit_period: plan.credit_period,
      next_grant_at: "2026-09-30T16:00:00Z",
      topup_allowed: planId !== "free",
      can_manage: true,
      queued: [],
    }
  }
  const providerView = {
    items: alipayTest
      ? [
          { id: "gateway", name: "测试支付渠道" },
          {
            id: "alipay",
            name: "支付宝",
            confirmation_mode: "query",
            supports_status_query: true,
            supports_cancel: true,
            refresh_checkout: true,
          },
        ]
      : [{ id: "gateway", name: "测试支付渠道" }],
  }
  const ordersView = () => {
    const plan = planOrderView()
    const items = plan ? [plan, order()] : [order()]
    return { items, total: items.length, total_pages: 1, page: 1, page_size: 10 }
  }
  async function cancelPlanOrder(route: Route) {
    if (cancelError) {
      await route.fulfill({ status: 502, json: { detail: { code: "PAYMENT_CANCEL_FAILED" } } })
      return
    }
    if (confirmOnQuery) planPaid = true
    else planCancelled = true
    await route.fulfill({ json: planOrderView() })
  }
  await page.route("https://checkout.example.test/**", (route) =>
    route.fulfill({ contentType: "text/html", body: "<h1>测试支付页面</h1>" }),
  )
  await page.addInitScript(() => localStorage.setItem("bossip:lang", "zh-CN"))
  await page.route(
    (url) => url.pathname.startsWith("/api/"),
    async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      const path = url.pathname
      let data: unknown = []
      if (path === "/api/auth/refresh") data = { access_token: "fixture-token" }
      else if (path === "/api/auth/me")
        data = { id: "payer", username: "测试用户", role: "user", is_active: true }
      else if (path === "/api/auth/me/preferences") data = { language: "zh-CN" }
      else if (path === "/api/workspaces")
        data = {
          items: [
            { id: "ws-fixture", name: "个人空间", kind: "personal", role: "owner", owner_user_id: "payer" },
          ],
          default_workspace_id: "ws-fixture",
        }
      else if (path === "/api/agent/config") data = { models: [], agents: [] }
      else if (path === "/api/cron/status") data = { enabled: false, jobs: 0 }
      else if (path === "/api/billing/balance") data = balanceView()
      else if (path === "/api/billing/plans") data = catalog
      else if (path === "/api/billing/subscription") data = subscriptionView()
      else if (path === "/api/billing/summary") {
        summaryRequests.push(url)
        const selected = selectedRecords(url)
        data = {
          total_tokens: selected.length * 15000,
          total_credits: (selected.length * 0.00412).toFixed(5),
          charged_credits: (selected.length * 0.00412).toFixed(5),
          historical_count: 0,
          unpriced_count: 0,
        }
      } else if (path === "/api/billing/providers") data = providerView
      else if (path === "/api/billing/usage") {
        usageRequests.push(url)
        const page = Number(url.searchParams.get("page") ?? "1")
        const pageSize = Number(url.searchParams.get("page_size") ?? "20")
        const selected = selectedRecords(url)
        data = {
          total: selected.length,
          total_pages: Math.max(1, Math.ceil(selected.length / pageSize)),
          page,
          page_size: pageSize,
          items: selected.slice((page - 1) * pageSize, page * pageSize),
        }
      } else if (path === "/api/billing/orders" && request.method() === "POST") {
        newOrders += 1
        const body = request.postDataJSON()
        submitted.push(body)
        if (body.kind === "subscription") {
          const plan = catalog.plans.find((item) => item.id === body.plan_id)!
          planOrder = {
            id: "pay-plan",
            kind: "subscription",
            provider: body.provider,
            plan_id: body.plan_id,
            cycle: body.cycle,
            amount_fen: plan.prices_fen[body.cycle as "monthly" | "yearly"],
            currency: "CNY",
            credits: plan.credits,
            created_at: "2026-09-05T01:00:00Z",
            paid_at: null,
            checkout_url: "https://checkout.example.test/plan",
          }
          data = planOrderView()
        } else {
          checkoutReady = true
          data = order()
        }
      } else if (path === "/api/billing/orders") data = ordersView()
      else if (path === "/api/billing/orders/pay-existing/checkout") {
        resumed.push(path)
        checkoutReady = true
        data = order()
      } else if (path === "/api/billing/orders/pay-existing") data = order()
      else if (path === "/api/billing/orders/pay-plan") data = planOrderView()
      else if (path === "/api/billing/orders/pay-plan/checkout") {
        resumed.push(path)
        planOrder!.checkout_url = "https://checkout.example.test/refreshed-plan"
        data = planOrderView()
      } else if (path === "/api/billing/orders/pay-plan/cancel") {
        await cancelPlanOrder(route)
        return
      } else if (path === "/api/billing/orders/pay-plan/refresh") {
        await queryPlanOrder(route)
        return
      }
      await route.fulfill({ json: data })
    },
  )
  return {
    markPaid: () => {
      if (planOrder) planPaid = true
      else paid = true
    },
    newOrderCount: () => newOrders,
    resumed,
    submitted,
    usageRequests,
    summaryRequests,
    queries,
    failCancel: (value: boolean) => {
      cancelError = value
    },
    failQuery: (value: boolean) => {
      queryError = value
    },
    confirmOnQuery: () => {
      confirmOnQuery = true
    },
  }
}
