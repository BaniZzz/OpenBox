import { expect, test } from "@playwright/test"
import { billingApi } from "./helpers/billing"

// All APIs are local fixtures; these tests never open a real payment checkout.
test.use({ storageState: { cookies: [], origins: [] }, timezoneId: "Asia/Shanghai" })

test("usage shows credits, model and server pagination at desktop and narrow widths", async ({
  page,
}, info) => {
  await billingApi(page)
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto("/app/settings/usage")
  await expect(page).toHaveURL(/\/app\/billing\/usage$/)
  await expect(page.getByRole("button", { name: "订购", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  )
  await expect(page.getByText("88.125 积分", { exact: true })).toBeVisible()
  const usage = page.getByRole("region", { name: "消耗明细", exact: true })
  await expect(usage.getByRole("listitem")).toHaveCount(20)
  await expect(usage.getByText("gpt-5.6-luna", { exact: true }).first()).toBeVisible()
  await expect(page.locator("body")).not.toContainText(/US\$|USD|人民币|￥/)
  await expect(page.locator("body")).not.toContainText(
    /缓存包含在输入|暂未从余额扣除|历史记录按|充值渠道接入后/,
  )
  await page.getByRole("navigation", { name: "用量分页" }).getByRole("button", { name: "下一页" }).click()
  await expect(usage.getByRole("listitem")).toHaveCount(1)
  await expect(usage.getByRole("link", { name: "测试会话 21", exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath("billing-desktop.png") })
  await page.setViewportSize({ width: 635, height: 805 })
  await expect(page.getByText("88.125 积分", { exact: true })).toBeVisible()
  expect(await usage.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true)
  expect(await page.locator("body").evaluate((element) => element.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await expect(page.getByLabel("开始日期")).toBeVisible()
  await expect(page.getByLabel("结束日期")).toBeVisible()
  await page.screenshot({ path: info.outputPath("billing-narrow.png") })
})

test("Alipay defaults, immediate checkout and persisted order recovery", async ({ page }, info) => {
  const api = await billingApi(page, "free", true)
  await page.setViewportSize({ width: 635, height: 805 })
  await page.goto("/app/billing/purchase")
  const pro = page.getByRole("article", { name: "专业版", exact: true })
  const max = page.getByRole("article", { name: "旗舰版", exact: true })
  await expect(pro).toContainText("¥0.1")
  await expect(max).toContainText("¥0.1")
  const channels = page.getByRole("group", { name: "支付渠道" })
  await expect(channels.getByRole("button", { name: "支付宝", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  )
  await channels.getByRole("button", { name: "测试支付渠道", exact: true }).click()
  await expect(channels.getByRole("button", { name: "测试支付渠道", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  )
  await channels.getByRole("button", { name: "支付宝", exact: true }).click()
  await expect(page.getByRole("button", { name: "查询支付状态", exact: true })).toHaveCount(0)
  await page.screenshot({ path: info.outputPath("purchase-channels-narrow.png") })
  await pro.getByRole("button", { name: "订购套餐", exact: true }).click()
  await expect(page).toHaveURL("https://checkout.example.test/plan")
  expect(api.submitted[0]).toMatchObject({ provider: "alipay", plan_id: "pro", cycle: "monthly" })
  expect(api.submitted[0]).not.toHaveProperty("amount_fen")
  await page.goBack()
  await expect(page).toHaveURL(/\/app\/billing\/orders$/)
  const order = page.getByRole("listitem").filter({ hasText: "订单号：pay-plan" })
  await order.getByRole("button", { name: "继续支付", exact: true }).click()
  await expect(page).toHaveURL("https://checkout.example.test/refreshed-plan")
  expect(api.newOrderCount()).toBe(1)
  await page.goBack()
  const query = order.getByRole("button", { name: "查询支付状态", exact: true })
  await query.click()
  await expect(order.getByText("订单尚未支付，完成付款后可再次查询。")).toBeVisible()
  await expect(page.getByText("剩余 10 积分", { exact: true })).toBeVisible()
  api.failQuery(true)
  await query.click()
  await expect(order.getByRole("alert")).toHaveText("支付结果查询失败，请稍后重试。")
  await page.screenshot({ path: info.outputPath("orders-recovery-narrow.png") })
  api.failQuery(false)
  api.confirmOnQuery()
  await query.click()
  await expect(order.getByRole("status")).toHaveText("已支付")
  await expect(page.getByText("剩余 290 积分", { exact: true })).toBeVisible()
  await expect(order.getByRole("button")).toHaveCount(0)
  expect(api.queries.length).toBeGreaterThanOrEqual(3)
  expect(api.queries.every((workspace) => workspace === "ws-fixture")).toBe(true)
  expect(await page.locator("body").evaluate((el) => el.scrollWidth <= window.innerWidth)).toBe(true)
})

test("sidebar opens purchase and date filters reset pagination and totals", async ({ page }) => {
  const api = await billingApi(page)
  await page.goto("/app/billing/usage")
  await page.getByRole("button", { name: "订购", exact: true }).click()
  await expect(page).toHaveURL(/\/app\/billing$/)
  await expect(page.getByRole("region", { name: "积分订购", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "充值", exact: true })).toBeVisible()
  await page
    .getByRole("navigation", { name: "订购", exact: true })
    .getByRole("link", { name: "用量与消耗" })
    .click()
  const usage = page.getByRole("region", { name: "消耗明细", exact: true })
  await expect(usage.getByRole("listitem")).toHaveCount(20)
  await page.getByRole("navigation", { name: "用量分页" }).getByRole("button", { name: "下一页" }).click()
  await expect(page.getByText("2 / 2 页", { exact: true })).toBeVisible()
  await page.getByLabel("开始日期").fill("2026-09-04")
  await page.getByLabel("结束日期").fill("2026-09-04")
  await page.getByRole("button", { name: "筛选", exact: true }).click()
  await expect(page.getByText("1 / 1 页", { exact: true })).toBeVisible()
  await expect(usage.getByRole("link", { name: "测试会话 21", exact: true })).toBeVisible()
  await expect(usage.getByRole("listitem")).toHaveCount(1)
  const balance = page.getByRole("region", { name: "当前空间可用积分" })
  await expect(balance).toContainText("所选时段 tokens")
  await expect(balance).toContainText("15k")
  await expect(balance).toContainText("0.00412")
  await expect(balance).toContainText("88.125 积分")
  for (const requests of [api.summaryRequests, api.usageRequests]) {
    const params = requests.at(-1)!.searchParams
    expect(params.get("date_from")).toBe("2026-09-04")
    expect(params.get("date_to")).toBe("2026-09-04")
    expect(params.get("tz")).toBe("Asia/Shanghai")
  }
  expect(api.usageRequests.at(-1)!.searchParams.get("page")).toBe("1")
  await page.getByLabel("开始日期").fill("2026-09-05")
  await page.getByRole("button", { name: "筛选", exact: true }).click()
  await expect(page.getByRole("alert")).toHaveText("开始日期不能晚于结束日期")
  await page.getByRole("button", { name: "重置", exact: true }).click()
  await expect(page.getByLabel("开始日期")).toHaveValue("")
  await expect(page.getByLabel("结束日期")).toHaveValue("")
  await expect(page.getByText("1 / 2 页", { exact: true })).toBeVisible()
  await expect(usage.getByRole("listitem")).toHaveCount(20)
  await expect(balance).toContainText("累计 tokens")
  await expect(balance).toContainText("315k")
  await page.getByLabel("结束日期").fill("2026-09-01")
  await page.getByRole("button", { name: "筛选", exact: true }).click()
  await expect(usage.getByText("所选日期内没有消耗记录")).toBeVisible()
})

test("reload resumes the same order and a confirmed payment refreshes the balance", async ({ page }) => {
  const api = await billingApi(page)
  await page.goto("/app/billing/orders")
  const history = page.getByRole("region", { name: "订单查询列表" })
  await expect(history.getByRole("button", { name: "继续支付" })).toBeVisible()
  await page.reload()
  await history.getByRole("button", { name: "继续支付" }).click()
  await expect(page).toHaveURL("https://checkout.example.test/existing")
  await page.goBack()
  await expect(page).toHaveURL(/\/app\/billing\/orders$/)
  expect(api.newOrderCount()).toBe(0)
  expect(api.resumed).toHaveLength(1)
  api.markPaid()
  await expect(history.getByRole("listitem").getByRole("status")).toHaveText("已支付", { timeout: 10_000 })
  await expect(history.getByRole("link")).toHaveCount(0)
  await expect(page.getByText("剩余 98.125 积分", { exact: true })).toBeVisible()
})

test("free workspaces can choose yearly plans and only gain paid benefits after payment", async ({
  page,
}, info) => {
  const api = await billingApi(page, "free")
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto("/app/billing/purchase")
  const pro = page.getByRole("article", { name: "专业版", exact: true })
  const max = page.getByRole("article", { name: "旗舰版", exact: true })
  await expect(
    page.getByRole("article", { name: "免费版", exact: true }).getByText("¥0", { exact: true }),
  ).toBeVisible()
  await expect(pro).toContainText("¥0.1")
  await expect(pro).toContainText("每月 280 积分")
  await expect(max).toContainText("¥0.1")
  await expect(max).toContainText("每月 1,680 积分")
  await expect(page.getByRole("button", { name: "充值", exact: true })).toHaveCount(0)
  await page.getByRole("button", { name: "年付", exact: true }).click()
  await expect(pro).toContainText("¥0.1")
  await expect(max).toContainText("¥0.1")
  await page.screenshot({ path: info.outputPath("plans-desktop.png") })
  await page.setViewportSize({ width: 635, height: 805 })
  expect(await page.locator("body").evaluate((el) => el.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath("plans-narrow.png") })
  await pro.getByRole("button", { name: "订购套餐", exact: true }).click()
  await expect(page).toHaveURL("https://checkout.example.test/plan")
  await page.goBack()
  await expect(page).toHaveURL(/\/app\/billing\/orders$/)
  expect(api.submitted).toHaveLength(1)
  expect(api.submitted[0]).toEqual({
    kind: "subscription",
    provider: "gateway",
    plan_id: "pro",
    cycle: "yearly",
    request_key: expect.any(String),
  })
  await expect(page.getByText("剩余 10 积分", { exact: true })).toBeVisible()
  api.markPaid()
  const purchased = page.getByRole("listitem").filter({ hasText: "订单号：pay-plan" })
  await expect(purchased.getByRole("status")).toHaveText("已支付", { timeout: 10000 })
  await page.getByRole("link", { name: "积分订购", exact: true }).click()
  await expect(page.getByText("当前套餐 · 专业版", { exact: true })).toBeAttached()
  const extra = page.getByRole("region", { name: "额外充值", exact: true })
  await expect(extra.getByRole("button", { name: "充值", exact: true })).toBeVisible()
  await extra.getByRole("button", { name: "50 积分", exact: true }).click()
  await expect(extra.getByLabel("充值积分")).toHaveValue("50")
  await expect(extra.getByLabel("充值积分")).toHaveAttribute("max", "100000")
})

test("order filters cover paid, unpaid and cancelled orders with pagination", async ({ page }, info) => {
  await billingApi(page)
  const requests: URL[] = []
  const rows = Array.from({ length: 12 }, (_, index) => ({
    id: "pay-filter-" + index,
    provider: "gateway",
    kind: "topup",
    amount_fen: 1000,
    credits: "10",
    status: index === 11 ? "cancelled" : index === 10 ? "paid" : "pending",
    checkout_url: index < 10 ? "https://checkout.example.test/one" : null,
    created_at: "2026-09-05T01:00:00Z",
    paid_at: null,
  }))
  await page.route("**/api/billing/orders?**", async (route) => {
    const url = new URL(route.request().url())
    requests.push(url)
    const params = url.searchParams
    const selected = rows.filter(
      (row) =>
        (!params.get("status") || row.status === params.get("status")) &&
        (!params.get("provider") || row.provider === params.get("provider")) &&
        (!params.get("order_id") || row.id.includes(params.get("order_id")!)) &&
        (!params.get("date_from") || params.get("date_from")! <= "2026-09-05") &&
        (!params.get("date_to") || params.get("date_to")! >= "2026-09-05"),
    )
    const current = Number(params.get("page"))
    const size = Number(params.get("page_size"))
    await route.fulfill({
      json: {
        items: selected.slice((current - 1) * size, current * size),
        total: selected.length,
        total_pages: Math.max(1, Math.ceil(selected.length / size)),
        page: current,
        page_size: size,
      },
    })
  })
  await page.setViewportSize({ width: 919, height: 805 })
  await page.goto("/app/billing/orders")
  const list = page.getByRole("region", { name: "订单查询列表" })
  const statuses = list.getByRole("group", { name: "订单状态" })
  await expect(list.getByRole("listitem")).toHaveCount(10)
  await list.getByRole("button", { name: "下一页", exact: true }).click()
  await expect(list.getByRole("listitem")).toHaveCount(2)
  await statuses.getByRole("button", { name: "已取消", exact: true }).click()
  await expect(list.getByRole("listitem")).toHaveCount(1)
  await expect(list.getByRole("listitem").getByRole("status")).toHaveText("已取消")
  await expect(list.getByRole("listitem").getByRole("button")).toHaveCount(0)
  expect(requests.at(-1)!.searchParams.get("page")).toBe("1")
  await statuses.getByRole("button", { name: "已支付", exact: true }).click()
  await expect(list.getByRole("listitem").getByRole("status")).toHaveText("已支付")
  await expect(list.getByRole("listitem").getByRole("button")).toHaveCount(0)
  await statuses.getByRole("button", { name: "待支付", exact: true }).click()
  await expect(list.getByRole("listitem")).toHaveCount(10)
  await list.getByLabel("订单号", { exact: true }).fill("pay-filter-3")
  await list.getByRole("combobox", { name: "支付渠道", exact: true }).selectOption("gateway")
  await list.getByLabel("开始日期").fill("2026-09-05")
  await list.getByLabel("结束日期").fill("2026-09-05")
  await list.getByRole("button", { name: "筛选", exact: true }).click()
  await expect(list.getByRole("listitem")).toHaveCount(1)
  expect(Object.fromEntries(requests.at(-1)!.searchParams)).toMatchObject({
    status: "pending",
    provider: "gateway",
    order_id: "pay-filter-3",
    date_from: "2026-09-05",
    date_to: "2026-09-05",
    tz: "Asia/Shanghai",
    page: "1",
  })
  await page.screenshot({ path: info.outputPath("orders-filtered.png") })
  await list.getByRole("button", { name: "重置", exact: true }).click()
  await expect(list.getByRole("listitem")).toHaveCount(10)
  await list.getByRole("combobox", { name: "每页", exact: true }).selectOption("20")
  await expect(list.getByRole("listitem")).toHaveCount(12)
  await list.getByLabel("订单号", { exact: true }).fill("does-not-exist")
  await list.getByRole("button", { name: "筛选", exact: true }).click()
  await expect(list.getByText("没有符合条件的订单")).toBeVisible()
  await page.setViewportSize({ width: 635, height: 805 })
  expect(await page.locator("body").evaluate((el) => el.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath("orders-filters-narrow.png") })
})

test("returning from checkout automatically reconciles payment without a manual query", async ({ page }) => {
  const api = await billingApi(page, "free", true)
  await page.goto("/app/billing/purchase")
  await page
    .getByRole("article", { name: "专业版", exact: true })
    .getByRole("button", { name: "订购套餐" })
    .click()
  await expect(page).toHaveURL("https://checkout.example.test/plan")
  api.confirmOnQuery()
  await page.goBack()
  const order = page.getByRole("listitem").filter({ hasText: "订单号：pay-plan" })
  await expect(order.getByRole("status")).toHaveText("已支付")
  await expect(order.getByRole("button")).toHaveCount(0)
  await expect(page.getByText("剩余 290 积分", { exact: true })).toBeVisible()
})

test("cancel payment waits for the server and removes payment actions after confirmation", async ({
  page,
}, info) => {
  const api = await billingApi(page, "free", true)
  await page.goto("/app/billing/purchase")
  await page
    .getByRole("article", { name: "专业版", exact: true })
    .getByRole("button", { name: "订购套餐" })
    .click()
  await expect(page).toHaveURL("https://checkout.example.test/plan")
  await page.goBack()
  const order = page.getByRole("listitem").filter({ hasText: "订单号：pay-plan" })
  api.failCancel(true)
  await order.getByRole("button", { name: "取消支付", exact: true }).click()
  await expect(order.getByRole("alert")).toContainText("暂未确认取消")
  await expect(order.getByRole("status").first()).toHaveText("待支付")
  api.failCancel(false)
  await order.getByRole("button", { name: "取消支付", exact: true }).click()
  await expect(order.getByRole("status")).toHaveText("已取消")
  await expect(order.getByRole("button")).toHaveCount(0)
  await expect(page.getByText("剩余 10 积分", { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 635, height: 805 })
  await page.screenshot({ path: info.outputPath("cancelled-order-narrow.png") })
  await page.reload()
  await expect(order.getByRole("status")).toHaveText("已取消")
  expect(api.newOrderCount()).toBe(1)
})

test("focus on orders queries the gateway again and a paid response wins over cancellation", async ({
  page,
}) => {
  const api = await billingApi(page, "free", true)
  await page.goto("/app/billing/purchase")
  await page
    .getByRole("article", { name: "专业版", exact: true })
    .getByRole("button", { name: "订购套餐" })
    .click()
  await expect(page).toHaveURL("https://checkout.example.test/plan")
  await page.goBack()
  const order = page.getByRole("listitem").filter({ hasText: "订单号：pay-plan" })
  await expect(order.getByRole("button", { name: "取消支付" })).toBeVisible()
  await expect.poll(() => api.queries.length).toBeGreaterThan(0)
  const count = api.queries.length
  await page.evaluate(() => window.dispatchEvent(new Event("focus")))
  await expect.poll(() => api.queries.length).toBeGreaterThan(count)
  api.confirmOnQuery()
  await order.getByRole("button", { name: "取消支付" }).click()
  await expect(order.getByRole("status")).toHaveText("已支付")
  await expect(order.getByRole("button")).toHaveCount(0)
})

test("cancelling the last pending order on a later page returns to a valid page", async ({ page }) => {
  await billingApi(page)
  const rows = Array.from({ length: 11 }, (_, index) => ({
    id: "pay-last-" + index,
    provider: "gateway",
    kind: "topup",
    amount_fen: 1000,
    credits: "10",
    status: "pending",
    checkout_url: null,
    created_at: "2026-09-05T01:00:00Z",
    paid_at: null,
  }))
  await page.route("**/api/billing/providers", (route) =>
    route.fulfill({ json: { items: [{ id: "gateway", name: "测试支付渠道", supports_cancel: true }] } }),
  )
  await page.route("**/api/billing/orders?**", (route) => {
    const params = new URL(route.request().url()).searchParams
    const selected = rows.filter((row) => !params.get("status") || row.status === params.get("status"))
    const current = Number(params.get("page"))
    return route.fulfill({
      json: {
        items: selected.slice((current - 1) * 10, current * 10),
        total: selected.length,
        total_pages: Math.max(1, Math.ceil(selected.length / 10)),
        page: current,
        page_size: 10,
      },
    })
  })
  await page.route("**/api/billing/orders/pay-last-10/cancel", (route) => {
    rows[10].status = "cancelled"
    return route.fulfill({ json: rows[10] })
  })
  await page.goto("/app/billing/orders")
  const list = page.getByRole("region", { name: "订单查询列表" })
  await list
    .getByRole("group", { name: "订单状态" })
    .getByRole("button", { name: "待支付", exact: true })
    .click()
  await list.getByRole("button", { name: "下一页" }).click()
  await expect(list.getByRole("listitem")).toHaveCount(1)
  await list.getByRole("button", { name: "取消支付" }).click()
  await expect(list.getByText("1 / 1 页", { exact: true })).toBeVisible()
  await expect(list.getByRole("listitem")).toHaveCount(10)
})

test("legacy uncreated orders stay cancelled after reload and keep checking late payment", async ({
  page,
}) => {
  await billingApi(page)
  const row = {
    id: "pay-legacy-uncreated",
    provider: "alipay",
    kind: "subscription",
    plan_id: "pro",
    cycle: "monthly",
    amount_fen: 10,
    currency: "CNY",
    credits: "280",
    status: "pending",
    checkout_url: "https://checkout.example.test/legacy",
    created_at: "2026-09-05T14:01:00Z",
    paid_at: null as string | null,
    cancelled_at: null as string | null,
    cancellation_reason: null as string | null,
    reconcile_required: false,
  }
  let queries = 0
  let paid = false
  await page.route("**/api/billing/providers", (route) =>
    route.fulfill({
      json: { items: [{ id: "alipay", name: "支付宝", supports_cancel: true, supports_status_query: true }] },
    }),
  )
  await page.route("**/api/billing/orders?**", (route) => {
    const status = new URL(route.request().url()).searchParams.get("status")
    const items = !status || status === row.status ? [row] : []
    return route.fulfill({ json: { items, total: items.length, total_pages: 1, page: 1, page_size: 10 } })
  })
  await page.route("**/api/billing/orders/pay-legacy-uncreated/cancel", (route) => {
    Object.assign(row, {
      status: "cancelled",
      checkout_url: null,
      cancelled_at: "2026-09-06T03:00:00Z",
      cancellation_reason: "trade_not_created",
      reconcile_required: true,
    })
    return route.fulfill({ json: row })
  })
  await page.route("**/api/billing/orders/pay-legacy-uncreated/refresh", (route) => {
    queries += 1
    if (paid)
      Object.assign(row, { status: "paid", paid_at: "2026-09-06T03:10:00Z", reconcile_required: false })
    return route.fulfill({ json: row })
  })
  await page.goto("/app/billing/orders")
  const list = page.getByRole("region", { name: "订单查询列表" })
  const order = list.getByRole("listitem")
  await expect(order).toContainText("2026年9月5日 22:01")
  await order.getByRole("button", { name: "取消支付" }).click()
  await expect(order.getByRole("status")).toHaveText("已取消")
  await expect(order).toContainText("取消时间 2026年9月6日 11:00")
  await expect(order).toContainText("请关闭此前打开的支付宝页面")
  await expect(order.getByRole("button")).toHaveCount(0)
  await page.reload()
  await expect(order.getByRole("status")).toHaveText("已取消")
  await list.getByRole("group", { name: "订单状态" }).getByRole("button", { name: "已取消" }).click()
  await expect(order).toHaveCount(1)
  const before = queries
  await page.evaluate(() => window.dispatchEvent(new Event("focus")))
  await expect.poll(() => queries).toBeGreaterThan(before)
  paid = true
  await page.evaluate(() => window.dispatchEvent(new Event("focus")))
  await expect(list.getByText("没有符合条件的订单")).toBeVisible()
  await list.getByRole("group", { name: "订单状态" }).getByRole("button", { name: "已支付" }).click()
  await expect(order.getByRole("status")).toHaveText("已支付")
  await expect(order.getByRole("button")).toHaveCount(0)
  await expect(order.getByText("请关闭此前打开的支付宝页面", { exact: false })).toHaveCount(0)
})
