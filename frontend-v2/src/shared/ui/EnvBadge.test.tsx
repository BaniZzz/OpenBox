import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { EnvBadge } from "./EnvBadge"

const query = vi.fn()
vi.mock("@/shared/api/environment", () => ({ useEnvironmentQuery: () => query() }))
vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: (key: string) => key }) }))

afterEach(() => {
  cleanup()
  query.mockReset()
})

describe("EnvBadge", () => {
  it("names a staging deployment", () => {
    query.mockReturnValue({ data: { name: "staging" } })
    render(<EnvBadge />)
    expect(screen.getByTestId("env-badge").textContent).toBe("env.staging")
  })

  it("renders nothing for production or unknown", () => {
    query.mockReturnValue({ data: { name: "prod" } })
    render(<EnvBadge />)
    expect(screen.queryByTestId("env-badge")).toBeNull()
  })

  it("renders nothing before the environment is known", () => {
    query.mockReturnValue({ data: undefined })
    render(<EnvBadge />)
    expect(screen.queryByTestId("env-badge")).toBeNull()
  })
})
