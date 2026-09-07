import { defineConfig } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  testMatch: "desktop-activation.spec.ts",
  workers: 1,
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:4317",
    channel: "chromium",
    locale: "zh-CN",
    viewport: { width: 1280, height: 800 },
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4317",
    url: "http://127.0.0.1:4317",
    reuseExistingServer: false,
  },
})
