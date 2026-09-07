import { defineConfig } from "@playwright/test"
import isolatedConfig from "./playwright.desktop.config"

// Only mocked billing APIs; no shared dev server, login or real payment gateway.
export default defineConfig({
  ...isolatedConfig,
  testMatch: ["billing.spec.ts", "billing-checkout.spec.ts"],
})
