import { afterEach, describe, expect, it, vi } from "vitest"
import type { LogtoConfig } from "@/shared/api/logto"
import { beginLogtoLogin } from "./logto"

const config: LogtoConfig = {
  enabled: true,
  endpoint: "https://auth.example.test",
  issuer: "https://auth.example.test/oidc",
  app_id: "web-app-id",
  redirect_uri: "https://app.example.test/callback",
  post_logout_redirect_uri: "https://app.example.test",
}

afterEach(() => sessionStorage.clear())

describe("beginLogtoLogin", () => {
  it("forces an interactive login so a stale SSO cookie cannot restore the old account", async () => {
    const redirect = vi.fn<(url: string) => void>()

    await beginLogtoLogin(config, { redirect })

    expect(redirect).toHaveBeenCalledOnce()
    const target = new URL(redirect.mock.calls[0][0])
    expect(`${target.origin}${target.pathname}`).toBe("https://auth.example.test/oidc/auth")
    expect(target.searchParams.get("client_id")).toBe("web-app-id")
    expect(target.searchParams.get("prompt")?.split(" ")).toEqual(["login", "consent"])
    expect(target.searchParams.get("code_challenge_method")).toBe("S256")
  })
})
