"""Orders and paid receipts. Browser redirects never credit an account."""
import os
from decimal import Decimal
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from billing.providers import PaidReceipt, CancelledReceipt, VerifiedReceipt, TradeNotCreated, get_provider
from billing.plans import plan_catalog
from billing.service import BillingError, lock_balance, now, post_ledger
from billing.subscriptions import apply_subscription, require_topup_allowed
from core.identifier import ascending as generate_id
from db.base import get_db_session
from db.models.billing import PaymentOrder, PaymentOrderRequest


def order_view(order: PaymentOrder) -> dict:
    product = order.product or {}
    return {"id": order.id, "provider": order.provider, "credits": str(order.credits),
            "status": order.status, "checkout_url": order.checkout_url if order.status == "pending" else None,
            "created_at": order.created_at, "paid_at": order.paid_at,
            "cancelled_at": order.cancelled_at, "cancellation_reason": order.cancellation_reason,
            "reconcile_required": order.status == "cancelled" and order.cancellation_reason == "trade_not_created",
            "kind": order.kind, "amount_fen": order.amount_fen, "currency": order.currency,
            "plan_id": product.get("plan", {}).get("id"), "cycle": product.get("cycle"),
            "starts_at": product.get("starts_at"), "ends_at": product.get("ends_at")}


def callback_url(provider_name: str) -> str | None:
    provider = get_provider(provider_name)
    if getattr(provider, "confirmation_mode", "callback") == "query":
        if not callable(getattr(provider, "query_payment", None)):
            raise BillingError("PAYMENT_UNAVAILABLE", "Query confirmation requires signed payment queries")
        return None
    public_url = os.environ.get("PAYMENT_PUBLIC_BASE_URL", "").rstrip("/")
    parsed = urlsplit(public_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise BillingError("PAYMENT_UNAVAILABLE", "Configure an HTTPS payment callback base URL")
    return f"{public_url}/api/billing/webhooks/{provider_name}"


def _matches_request(order, *, kind, provider_name, user_id, amount_fen, plan_id, cycle):
    product = order.product or {}
    same_product = (order.amount_fen == amount_fen if kind == "topup" else
                    (product.get("plan", {}).get("id"), product.get("cycle")) == (plan_id, cycle))
    return (order.kind, order.provider, order.user_id) == (kind, provider_name, user_id) and same_product


async def create_order(*, workspace_id: str, user_id: str, provider_name: str,
                       request_key: str, amount_fen: int | None = None,
                       kind: str = "topup", plan_id: str | None = None, cycle: str | None = None) -> dict:
    get_provider(provider_name)
    callback_url(provider_name)
    async with get_db_session() as db:
        # Serializes checkout creation with settlement and other checkout tabs.
        await lock_balance(db, workspace_id)
        attempt = await db.get(PaymentOrderRequest, (workspace_id, request_key))
        order = (await db.get(PaymentOrder, attempt.order_id) if attempt else
                 (await db.scalars(select(PaymentOrder).where(
                     PaymentOrder.workspace_id == workspace_id,
                     PaymentOrder.request_key == request_key))).one_or_none())
        if order is not None:
            if not _matches_request(order, kind=kind, provider_name=provider_name, user_id=user_id,
                                    amount_fen=amount_fen, plan_id=plan_id, cycle=cycle):
                raise BillingError("PAYMENT_IDEMPOTENCY_CONFLICT", "This request key belongs to a different order")
        else:
            catalog = plan_catalog()
            product = None
            if kind == "subscription":
                if plan_id not in {"pro", "max"} or cycle not in {"monthly", "yearly"}:
                    raise BillingError("INVALID_PLAN", "请选择有效的套餐和账期")
                plan = catalog.plan(plan_id)
                amount_fen, credits = plan.prices_fen[cycle], plan.credits
                product = {"plan": plan.model_dump(mode="json"), "cycle": cycle, "version": catalog.version}
            elif kind == "topup":
                if type(amount_fen) is not int or not catalog.topup.min_amount_fen <= amount_fen <= catalog.topup.max_amount_fen:
                    raise BillingError("INVALID_TOPUP_AMOUNT", "充值金额超出允许范围")
                await require_topup_allowed(db, workspace_id, now())
                credits = Decimal(amount_fen) / 100
            else:
                raise BillingError("INVALID_PLAN", "未知订购类型")
            candidates = (await db.scalars(select(PaymentOrder).where(
                PaymentOrder.workspace_id == workspace_id, PaymentOrder.user_id == user_id,
                PaymentOrder.provider == provider_name, PaymentOrder.kind == kind,
                PaymentOrder.status == "pending", PaymentOrder.amount_fen == amount_fen,
                PaymentOrder.credits == credits
            ).order_by(PaymentOrder.created_at.desc(), PaymentOrder.id.desc()))).all()
            # Keep snapshots immutable; a changed price/catalog is a new purchase.
            order = next((candidate for candidate in candidates if candidate.product == product), None)
            if order is None:
                order = PaymentOrder(id=generate_id("pay"), workspace_id=workspace_id,
                    user_id=user_id, request_key=request_key, provider=provider_name,
                    amount_fen=amount_fen, currency="CNY", credits=credits, kind=kind, product=product,
                    status="pending", created_at=now())
                db.add(order)
                await db.flush()
        if attempt is None:
            db.add(PaymentOrderRequest(workspace_id=workspace_id, request_key=request_key, order_id=order.id))
        if order.status != "pending":
            return order_view(order)
        order_id = order.id
    return await continue_order(workspace_id=workspace_id, user_id=user_id, order_id=order_id)


async def continue_order(*, workspace_id: str, user_id: str, order_id: str) -> dict:
    """Recover a checkout after navigation or an uncertain upstream response."""
    async with get_db_session() as db:
        order = await db.get(PaymentOrder, order_id)
        if order is None or order.workspace_id != workspace_id or order.user_id != user_id:
            raise BillingError("PAYMENT_ORDER_NOT_FOUND", "Order not found")
        if order.status == "paid":
            return order_view(order)
        if order.status == "cancelled":
            raise BillingError("PAYMENT_ORDER_CANCELLED", "This payment order is closed")
        provider_name, amount_fen = order.provider, order.amount_fen
        provider = get_provider(provider_name)
        existing_checkout = order.checkout_url
    if existing_checkout and callable(getattr(provider, "query_payment", None)):
        current = await refresh_order(workspace_id=workspace_id, user_id=user_id, order_id=order_id)
        if current["status"] != "pending":
            return current
    if existing_checkout and not getattr(provider, "refresh_checkout", False):
        async with get_db_session() as db:
            return order_view(await db.get(PaymentOrder, order_id))
    # Network outside the DB transaction. A timeout can be retried with the SAME
    # order id; the adapter contract requires the provider to deduplicate it.
    checkout = await provider.create_checkout(order_id=order_id, amount_fen=amount_fen,
        callback_url=callback_url(provider_name))
    async with get_db_session() as db:
        await lock_balance(db, workspace_id)
        order = await db.get(PaymentOrder, order_id)
        # A callback or another checkout retry may have won the race.
        if order.status == "pending" and (not order.checkout_url or getattr(provider, "refresh_checkout", False)):
            order.checkout_url = checkout.url
            order.provider_order_id = checkout.provider_order_id
        return order_view(order)


async def create_app_checkout(*, workspace_id: str, user_id: str, order_id: str) -> dict:
    """Create an opaque native-SDK payload without trusting SDK callbacks.

    App payloads are intentionally ephemeral: persisting them in checkout_url
    would expose a non-URL value to web clients and unnecessarily retain a signed
    request. The merchant order id keeps repeated calls idempotent upstream.
    """
    async with get_db_session() as db:
        order = await db.get(PaymentOrder, order_id)
        if order is None or order.workspace_id != workspace_id or order.user_id != user_id:
            raise BillingError("PAYMENT_ORDER_NOT_FOUND", "Order not found")
        if order.status == "cancelled":
            raise BillingError("PAYMENT_ORDER_CANCELLED", "This payment order is closed")
        if order.status == "paid":
            return {"order": order_view(order), "provider": order.provider, "sdk_payload": None}
        provider_name, amount_fen = order.provider, order.amount_fen
    provider = get_provider(provider_name)
    creator = getattr(provider, "create_app_checkout", None)
    if not callable(creator):
        raise BillingError("PAYMENT_UNAVAILABLE", "This channel does not support native app checkout")
    checkout = await creator(order_id=order_id, amount_fen=amount_fen,
                             callback_url=callback_url(provider_name))
    if checkout.provider_order_id != order_id:
        raise BillingError("PAYMENT_INVALID_CHECKOUT", "Payment channel returned a different order")
    async with get_db_session() as db:
        await lock_balance(db, workspace_id)
        order = await db.get(PaymentOrder, order_id)
        if order.status == "cancelled":
            raise BillingError("PAYMENT_ORDER_CANCELLED", "This payment order is closed")
        if order.status == "paid":
            return {"order": order_view(order), "provider": provider_name, "sdk_payload": None}
        order.provider_order_id = checkout.provider_order_id
        return {"order": order_view(order), "provider": provider_name, "sdk_payload": checkout.payload}


async def refresh_order(*, workspace_id: str, user_id: str, order_id: str) -> dict:
    """Explicit recovery if an asynchronous notification has not arrived."""
    async with get_db_session() as db:
        order = await db.get(PaymentOrder, order_id)
        if order is None or order.workspace_id != workspace_id or order.user_id != user_id:
            raise BillingError("PAYMENT_ORDER_NOT_FOUND", "Order not found")
        if order.status == "paid":
            return order_view(order)
        provider_name = order.provider
        cancellation_pending = order.status == "cancelled" and order.cancellation_reason == "trade_not_created"
        amount_fen = order.amount_fen
    query = getattr(get_provider(provider_name), "query_payment", None)
    if query is None:
        raise BillingError("PAYMENT_UNAVAILABLE", "This channel does not support payment queries")
    receipt = await query(order_id)
    if cancellation_pending and receipt is None:
        # The old cashier has now created a WAIT_BUYER_PAY trade. Finish the
        # user's existing cancellation intent before it can be paid there.
        close = getattr(get_provider(provider_name), "close_payment", None)
        if callable(close):
            try:
                receipt = await close(order_id, amount_fen)
            except Exception:
                receipt = await query(order_id)
                if receipt is None or isinstance(receipt, TradeNotCreated):
                    raise
    if receipt is not None:
        # Even custom adapters must not be able to settle an unrelated order
        # through this payer-authorized query endpoint.
        if receipt.order_id != order_id:
            raise BillingError("PAYMENT_INVALID_RECEIPT", "Query returned a different order")
        if not isinstance(receipt, TradeNotCreated):
            await apply_receipt(provider_name, receipt)
    async with get_db_session() as db:
        return order_view(await db.get(PaymentOrder, order_id))


async def cancel_order(*, workspace_id: str, user_id: str, order_id: str) -> dict:
    # Query first: closing a cashier is not proof of non-payment, and a payment
    # can complete while the merchant's notification is still in transit.
    async with get_db_session() as db:
        order = await db.get(PaymentOrder, order_id)
        if order is None or order.workspace_id != workspace_id or order.user_id != user_id:
            raise BillingError("PAYMENT_ORDER_NOT_FOUND", "Order not found")
        if order.status == "paid" or (order.status == "cancelled" and order.cancellation_reason != "trade_not_created"):
            return order_view(order)
        provider_name, amount_fen = order.provider, order.amount_fen
    close = getattr(get_provider(provider_name), "close_payment", None)
    if not callable(close):
        raise BillingError("PAYMENT_UNAVAILABLE", "This channel does not support cancelling payments")
    current = await refresh_order(workspace_id=workspace_id, user_id=user_id, order_id=order_id)
    if current["status"] != "pending":
        return current
    try:
        receipt = await close(order_id, amount_fen)
    except Exception:
        # The close may race a successful payment or time out after acceptance.
        current = await refresh_order(workspace_id=workspace_id, user_id=user_id, order_id=order_id)
        if current["status"] != "pending":
            return current
        raise
    if not isinstance(receipt, (CancelledReceipt, TradeNotCreated)) or receipt.order_id != order_id:
        raise BillingError("PAYMENT_INVALID_RECEIPT", "Close returned a different order")
    if isinstance(receipt, TradeNotCreated):
        await cancel_uncreated_order(provider_name, receipt)
    else:
        await apply_receipt(provider_name, receipt)
    async with get_db_session() as db:
        return order_view(await db.get(PaymentOrder, order_id))


async def cancel_uncreated_order(provider_name: str, result: TradeNotCreated) -> None:
    """Cancel only the merchant order; an issued cashier can still report later."""
    async with get_db_session() as db:
        order = await db.get(PaymentOrder, result.order_id)
        if order is None or order.provider != provider_name:
            raise BillingError("PAYMENT_ORDER_NOT_FOUND", "Order not found for this payment channel")
        await lock_balance(db, order.workspace_id)
        await db.refresh(order)
        # An authenticated paid/closed notification can win this race.
        if order.status != "pending":
            return
        order.status = "cancelled"
        order.cancelled_at = now()
        order.cancellation_reason = "trade_not_created"
        order.checkout_url = None


async def apply_receipt(provider_name: str, receipt: VerifiedReceipt) -> dict:
    if isinstance(receipt, PaidReceipt):
        return await settle_payment(provider_name, receipt)
    if not isinstance(receipt, CancelledReceipt):
        raise BillingError("PAYMENT_INVALID_RECEIPT", "Unknown payment receipt")
    async with get_db_session() as db:
        order = await db.get(PaymentOrder, receipt.order_id)
        if order is None or order.provider != provider_name:
            raise BillingError("PAYMENT_ORDER_NOT_FOUND", "Order not found for this payment channel")
        await lock_balance(db, order.workspace_id)
        await db.refresh(order)
        if (receipt.amount_fen, receipt.currency) != (order.amount_fen, order.currency):
            raise BillingError("PAYMENT_AMOUNT_MISMATCH", "Receipt amount or currency differs from the order")
        # TRADE_CLOSED may also follow a full refund. Never reinterpret a paid
        # order as unpaid or revoke its ledger through the cancellation path.
        if order.status == "paid":
            return {"accepted": True, "ignored": True}
        duplicate = order.status == "cancelled"
        order.status = "cancelled"
        order.cancelled_at = order.cancelled_at or now()
        order.cancellation_reason = "gateway_closed"
        order.checkout_url = None
        return {"accepted": True, "duplicate": duplicate}


async def settle_payment(provider_name: str, receipt: PaidReceipt) -> dict:
    try:
        async with get_db_session() as db:
            order = await db.get(PaymentOrder, receipt.order_id)
            if order is None or order.provider != provider_name:
                raise BillingError("PAYMENT_ORDER_NOT_FOUND", "Order not found for this payment channel")
            account = await lock_balance(db, order.workspace_id)
            await db.refresh(order)  # another callback may have completed while waiting
            if (receipt.amount_fen, receipt.currency) != (order.amount_fen, order.currency):
                raise BillingError("PAYMENT_AMOUNT_MISMATCH", "Receipt amount or currency differs from the order")
            if order.status == "paid":
                if order.provider_payment_id != receipt.payment_id:
                    raise BillingError("PAYMENT_RECEIPT_CONFLICT", "Order already has a different payment")
                return {"accepted": True, "duplicate": True}
            order.status = "paid"
            order.paid_at = now()
            order.provider_payment_id = receipt.payment_id
            if order.kind == "subscription":
                await apply_subscription(db, account, order)
            else:
                post_ledger(db, account, amount=order.credits, kind="topup",
                            reference_id=order.id, key=f"payment:{order.id}")
            await db.flush()  # unique provider/payment-id checked before returning
            return {"accepted": True, "duplicate": False}
    except IntegrityError as exc:
        raise BillingError("PAYMENT_RECEIPT_CONFLICT", "Payment was already used by another order") from exc
