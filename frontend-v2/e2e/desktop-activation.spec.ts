import { expect, test } from "@playwright/test"

test("paid setup restores after reload and reports completion without any provisioning request", async ({
  page,
}) => {
  let step = "connecting"
  const writes: string[] = []
  await page.route("**/api/**", async (route) => {
    // Vite also serves source modules from /src/shared/api/*.ts.
    if (!new URL(route.request().url()).pathname.startsWith("/api/")) return route.continue()
    if (route.request().method() !== "GET") writes.push(route.request().url())
    if (!route.request().url().endsWith("/api/desktop/status")) return route.abort()
    return route.fulfill({
      json: {
        mode: "per_user",
        state: step === "ready" ? "running" : step,
        entitled: true,
        activation: {
          request_id: "fixture-payment",
          state: step === "ready" ? "ready" : "working",
          step,
          attempts: 1,
          error: null,
          updated_at: "2026-09-07T00:00:00Z",
          next_retry_at: "2026-09-07T00:00:30Z",
          can_retry: false,
        },
      },
    })
  })
  await page.goto("/e2e/fixtures/desktop-activation.html")
  const dialog = page.getByRole("dialog")
  await expect(dialog).toBeVisible()
  await expect(dialog.locator('[aria-current="step"]')).toContainText("验证 sandbox 连接")
  await page.screenshot({ path: "test-results/desktop-activation-progress.png" })
  await page.getByRole("button", { name: "继续对话" }).click()
  await expect(dialog).not.toBeVisible()
  await page.reload()
  await expect(dialog).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: "test-results/desktop-activation-mobile.png" })
  step = "ready"
  await expect(dialog.getByRole("heading")).toHaveText("无影云已就绪", { timeout: 8_000 })
  await page.getByRole("button", { name: "知道了" }).click()
  await page.reload()
  await expect(dialog).not.toBeVisible()
  expect(writes).toEqual([])
})
