import { expect, test } from "@playwright/test"
import { billingApi } from "./helpers/billing"

// Deliberately delayed fixtures exercise the request and navigation gaps.
// The actual pending-order reuse is also checked against PostgreSQL and Alipay.
test.use({ storageState: { cookies: [], origins: [] }, timezoneId: "Asia/Shanghai" })

function gate() {
  let release!: () => void
  const promise = new Promise<void>((resolve) => {
    release = resolve
  })
  return { promise, release }
}

test("subscription immediately shows a modal, blocks double clicks and survives the redirect", async ({
  page,
}, info) => {
  const api = await billingApi(page, "free", true)
  const create = gate()
  let requests = 0
  const departures: { path: string; modalOpen: boolean }[] = []
  await page.exposeFunction("recordCheckoutDeparture", (state) => departures.push(state))
  await page.addInitScript(() => {
    window.addEventListener("beforeunload", () => {
      const report = (
        window as typeof window & {
          recordCheckoutDeparture: (state: { path: string; modalOpen: boolean }) => Promise<void>
        }
      ).recordCheckoutDeparture
      // The desktop activation dialog also stays mounted while closed.
      void report({ path: window.location.pathname, modalOpen: !!document.querySelector("dialog[open]") })
    })
  })
  await page.route("**/api/billing/orders", async (route) => {
    requests++
    await create.promise
    await route.fallback()
  })
  await page.setViewportSize({ width: 635, height: 805 })
  await page.goto("/app/billing/purchase")
  const subscribe = page
    .getByRole("article", { name: "专业版", exact: true })
    .getByRole("button", { name: "订购套餐" })
  await expect(subscribe).toBeEnabled()
  // Same-event-loop clicks verify the synchronous lock, before disabled renders.
  await subscribe.evaluate((button: HTMLButtonElement) => {
    button.click()
    button.click()
    button.click()
  })
  const modal = page.getByRole("dialog", { name: "正在跳转支付页面" })
  await expect(modal).toBeVisible()
  await expect(modal).toContainText("请勿重复点击")
  await page.keyboard.press("Escape")
  await expect(modal).toBeVisible()
  await expect.poll(() => requests).toBe(1)
  await page.screenshot({ path: info.outputPath("checkout-progress-narrow.png") })
  create.release()
  await expect(page).toHaveURL("https://checkout.example.test/plan")
  // Capture at departure: Playwright otherwise waits for navigation to finish.
  expect(departures).toContainEqual({ path: "/app/billing/orders", modalOpen: true })
  expect(requests).toBe(1)
  await page.goBack()
  await expect(page).toHaveURL(/\/app\/billing\/orders$/)
  await expect(page.getByRole("dialog")).toHaveCount(0)
  const order = page.getByRole("listitem").filter({ hasText: "订单号：pay-plan" })
  await expect(order.getByRole("button", { name: "继续支付" })).toBeEnabled()
  await page.getByRole("link", { name: "积分订购", exact: true }).click()
  await subscribe.click()
  await expect(page).toHaveURL("https://checkout.example.test/plan")
  await page.goBack()
  await expect(order).toHaveCount(1)
  expect(requests).toBe(2)
  expect(api.submitted).toHaveLength(2)
  expect(api.submitted[1].request_key).not.toBe(api.submitted[0].request_key)
  await expect(page.getByRole("dialog")).toHaveCount(0)
})

test("a checkout error releases the modal and retry keeps the original request key", async ({ page }) => {
  await billingApi(page, "free", true)
  const response = gate()
  const keys: string[] = []
  await page.route("**/api/billing/orders", async (route) => {
    keys.push(route.request().postDataJSON().request_key)
    if (keys.length === 1) {
      await response.promise
      await route.fulfill({ status: 502, json: { detail: { code: "PAYMENT_CREATE_FAILED" } } })
    } else await route.fallback()
  })
  await page.goto("/app/billing/purchase")
  const subscribe = page
    .getByRole("article", { name: "专业版", exact: true })
    .getByRole("button", { name: "订购套餐" })
  await subscribe.click()
  await expect(page.getByRole("dialog", { name: "正在跳转支付页面" })).toBeVisible()
  response.release()
  const failure = page.getByRole("dialog", { name: "暂时无法打开支付页面" })
  await expect(failure).toBeVisible()
  await failure.getByRole("button", { name: "返回", exact: true }).click()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await subscribe.click()
  await expect(page).toHaveURL("https://checkout.example.test/plan")
  expect(keys).toHaveLength(2)
  expect(keys[1]).toBe(keys[0])
})

test("continuing an order shows progress before the API responds and does not create an order", async ({
  page,
}) => {
  const api = await billingApi(page)
  const response = gate()
  await page.route("**/api/billing/orders/pay-existing/checkout", async (route) => {
    await response.promise
    await route.fallback()
  })
  await page.goto("/app/billing/orders")
  const resume = page.getByRole("button", { name: "继续支付" })
  await expect(resume).toBeEnabled()
  await resume.evaluate((button: HTMLButtonElement) => {
    button.click()
    button.click()
  })
  await expect(page.getByRole("dialog", { name: "正在跳转支付页面" })).toBeVisible()
  response.release()
  await expect(page).toHaveURL("https://checkout.example.test/existing")
  expect(api.newOrderCount()).toBe(0)
  expect(api.resumed).toHaveLength(1)
  await page.goBack()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(resume).toBeEnabled()
})

test("top-up shares the checkout modal and repeated submit sends one request", async ({ page }) => {
  const api = await billingApi(page)
  const response = gate()
  await page.route("**/api/billing/orders", async (route) => {
    await response.promise
    await route.fallback()
  })
  await page.goto("/app/billing/purchase")
  const submit = page.getByRole("button", { name: "充值", exact: true })
  await expect(submit).toBeEnabled()
  await submit.evaluate((button: HTMLButtonElement) => {
    button.click()
    button.click()
  })
  await expect(page.getByRole("dialog", { name: "正在跳转支付页面" })).toBeVisible()
  response.release()
  await expect(page).toHaveURL("https://checkout.example.test/existing")
  expect(api.newOrderCount()).toBe(1)
})
