import { createContext, useContext } from "react"
import type { PaymentOrder } from "@/shared/api/billing"

export const CheckoutRedirectContext = createContext<
  ((prepare: () => Promise<PaymentOrder>) => Promise<void>) | null
>(null)

export function useCheckoutRedirect() {
  const checkout = useContext(CheckoutRedirectContext)
  if (!checkout) throw new Error("CheckoutRedirectProvider is missing")
  return checkout
}
