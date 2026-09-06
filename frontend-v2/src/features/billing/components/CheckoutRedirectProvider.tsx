import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react"
import { useNavigate } from "react-router"
import { useTranslation } from "react-i18next"
import type { PaymentOrder } from "@/shared/api/billing"
import { paths } from "@/shared/router/paths"
import { Spinner } from "@/shared/ui/Spinner"
import { CheckoutRedirectContext } from "../hooks/useCheckoutRedirect"

export function CheckoutRedirectProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation("billing")
  const navigate = useNavigate()
  const [phase, setPhase] = useState<"redirecting" | "failed" | null>(null)
  const active = useRef<symbol | null>(null)
  const dialog = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const bodyId = useId()
  const reset = useCallback(() => {
    active.current = null
    setPhase(null)
  }, [])

  useEffect(() => {
    const restore = (event: PageTransitionEvent) => {
      // Back/Forward may restore the entire document, including the open modal.
      if (event.persisted) reset()
    }
    window.addEventListener("pageshow", restore)
    return () => {
      window.removeEventListener("pageshow", restore)
      active.current = null // Ignore a response after leaving/switching workspace.
    }
  }, [reset])

  useEffect(() => {
    if (phase && !dialog.current?.open) dialog.current?.showModal()
    else if (!phase && dialog.current?.open) dialog.current.close()
  }, [phase])

  const checkout = useCallback(
    async (prepare: () => Promise<PaymentOrder>) => {
      // One lock for plans, top-ups and every history row. Acquire synchronously,
      // before React renders disabled buttons or the order request is sent.
      if (active.current) return
      const attempt = Symbol()
      active.current = attempt
      setPhase("redirecting")
      try {
        const order = await prepare()
        if (active.current !== attempt) return
        // The provider stays mounted across this internal route change.
        await navigate(paths.billing("orders"), { replace: true })
        if (active.current !== attempt) return
        if (order.status === "pending") {
          if (!order.checkout_url) throw new Error("Checkout URL is missing")
          window.location.assign(order.checkout_url)
        } else reset()
      } catch {
        if (active.current === attempt) {
          active.current = null
          setPhase("failed")
        }
      }
    },
    [navigate, reset],
  )

  return (
    <CheckoutRedirectContext value={checkout}>
      {children}
      <dialog
        ref={dialog}
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        onCancel={(event) => {
          if (phase === "redirecting") event.preventDefault()
          else reset()
        }}
        className="bg-card text-ink border-hair shadow-pop backdrop:bg-n900/40 fixed inset-0 m-auto w-100 max-w-[calc(100vw-2rem)] rounded-2xl border p-7"
      >
        <div className="flex flex-col items-center gap-4 text-center" aria-live="polite">
          {phase === "redirecting" && <Spinner className="size-9 border-[3px]" />}
          <h2 id={titleId} className="text-xl font-medium">
            {t(phase === "failed" ? "checkout.failed" : "checkout.redirecting")}
          </h2>
          <p id={bodyId} className="text-n600 text-sm leading-relaxed">
            {t(phase === "failed" ? "checkout.retryHint" : "checkout.waitHint")}
          </p>
          {phase === "failed" && (
            <button
              type="button"
              onClick={reset}
              className="bg-ink text-bg mt-1 rounded-full px-6 py-2.5 text-sm"
            >
              {t("checkout.close")}
            </button>
          )}
        </div>
      </dialog>
    </CheckoutRedirectContext>
  )
}
