"""Exercise the native payment boundary with ephemeral RSA keys, never live money."""
import base64
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlencode, urlsplit
from uuid import uuid4

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import FastAPI
from sqlalchemy import func, select

from api.billing import router
from auth.middleware import get_current_user
from billing.alipay import AlipayPaymentProvider
from billing.payments import callback_url, create_order
from billing.providers import get_provider, TradeNotCreated
from billing.service import BillingError
from core.identifier import ascending
from db.base import get_db_session
from db.models.billing import CreditBalance, CreditLedger, PaymentOrder
from db.repository.user_repo import PgUserRepo


@pytest.fixture
def alipay(monkeypatch, tmp_path):
    app_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    gateway_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = tmp_path / "app.pem"
    private_path.write_bytes(app_key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    private_path.chmod(0o600)
    public_path = tmp_path / "alipay.pem"
    public_path.write_bytes(gateway_key.public_key().public_bytes(serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo))
    config = {"kind": "alipay", "app_id": "2021000000000001", "seller_id": "2088000000000001",
              "private_key_file": str(private_path), "alipay_public_key_file": str(public_path)}
    monkeypatch.setenv("PAYMENT_PROVIDERS_JSON", json.dumps({"alipay": config}))
    monkeypatch.setenv("PAYMENT_PUBLIC_BASE_URL", "https://app.example.test")
    adapter = get_provider("alipay")
    trade_no = "20260905" + str(uuid4().int)

    def sign(raw):
        return base64.b64encode(gateway_key.sign(raw, padding.PKCS1v15(), hashes.SHA256())).decode()

    def notify(order_id="pay-test", **changes):
        fields = {"app_id": config["app_id"], "seller_id": config["seller_id"],
            "out_trade_no": order_id, "trade_no": trade_no, "total_amount": "0.10",
            "trade_status": "TRADE_SUCCESS", "notify_type": "trade_status_sync", "charset": "utf-8",
            "notify_time": "2026-09-05 12:00:00", "subject": "中文 & 测试 + 支付", **changes}
        raw = "&".join(f"{key}={value}" for key, value in sorted(fields.items()) if value != "").encode()
        return urlencode({**fields, "sign_type": "RSA2", "sign": sign(raw)}).encode()

    def response(*, method="query", **changes):
        fields = {"code": "10000", "out_trade_no": "pay-test", "trade_no": trade_no,
                  "trade_status": "TRADE_SUCCESS", "total_amount": "0.10", **changes}
        raw = json.dumps(fields, ensure_ascii=True)  # intentional spaces and escapes
        return '{"sign":' + json.dumps(sign(raw.encode())) + ', "alipay_trade_' + method + '_response":' + raw + '}'

    return SimpleNamespace(adapter=adapter, config=config, app_key=app_key,
                           sign=sign, notify=notify, response=response)


def verify_request(alipay, params):
    supplied = base64.b64decode(params["sign"])
    raw = "&".join(f"{key}={value}" for key, value in sorted(params.items()) if key != "sign" and value).encode()
    alipay.app_key.public_key().verify(supplied, raw, padding.PKCS1v15(), hashes.SHA256())


async def test_checkout_is_rsa2_signed_for_exact_test_amount_and_official_gateway(alipay):
    checkout = await alipay.adapter.create_checkout(order_id="pay-test", amount_fen=10,
        callback_url="https://app.example.test/api/billing/webhooks/alipay")
    url = urlsplit(checkout.url)
    assert url.scheme == "https" and url.hostname == "openapi.alipay.com" and url.path == "/gateway.do"
    assert len(checkout.url) < 2048
    params = dict(parse_qsl(url.query))
    verify_request(alipay, params)
    assert params["sign_type"] == "RSA2" and params["method"] == "alipay.trade.page.pay"
    assert params["notify_url"] == "https://app.example.test/api/billing/webhooks/alipay"
    assert params["return_url"] == "https://app.example.test/app/billing/orders"
    assert json.loads(params["biz_content"]) == {"out_trade_no": "pay-test", "total_amount": "0.10",
        "subject": "bossip 订购", "product_code": "FAST_INSTANT_TRADE_PAY"}
    assert checkout.provider_order_id == "pay-test"
    sandbox = AlipayPaymentProvider({**alipay.config, "environment": "sandbox"})
    assert "alipaydev.com" in (await sandbox.create_checkout(order_id="pay-test", amount_fen=20,
        callback_url="https://app.example.test/api/billing/webhooks/alipay")).url


async def test_app_checkout_is_server_signed_for_official_mobile_sdk(alipay):
    checkout = await alipay.adapter.create_app_checkout(order_id="pay-test", amount_fen=10,
        callback_url="https://app.example.test/api/billing/webhooks/alipay")
    params = dict(parse_qsl(checkout.payload))
    verify_request(alipay, params)
    assert params["method"] == "alipay.trade.app.pay"
    assert params["notify_url"] == "https://app.example.test/api/billing/webhooks/alipay"
    assert "return_url" not in params
    assert json.loads(params["biz_content"]) == {"out_trade_no": "pay-test", "total_amount": "0.10",
        "subject": "bossip 订购", "product_code": "QUICK_MSECURITY_PAY"}
    assert checkout.provider_order_id == "pay-test"


@pytest.mark.parametrize("change", [
    {"app_id": "2021000000000002"}, {"seller_id": "2088000000000002"},
    {"total_amount": "0.101"}, {"total_amount": "1e-1"}, {"total_amount": "-0.10"},
    {"total_amount": "NaN"}, {"trade_status": "paid"}, {"notify_type": "refund"},
])
async def test_signed_but_invalid_notifications_are_rejected(alipay, change):
    with pytest.raises(BillingError):
        await alipay.adapter.verify_webhook(alipay.notify(**change), {"content-type": "application/x-www-form-urlencoded"})


@pytest.mark.parametrize("mutate", [
    lambda body: body.replace(b"0.10", b"0.20"),
    lambda body: body + b"&total_amount=0.20",
    lambda body: body + b"&sign=bogus",
    lambda body: body.replace(b"RSA2", b"RSA"),
    lambda body: body + b"&x=%FF",
    lambda body: body + b"&x=%Q1",
])
async def test_tampered_ambiguous_and_badly_encoded_notifications_fail(alipay, mutate):
    with pytest.raises(BillingError):
        await alipay.adapter.verify_webhook(mutate(alipay.notify()), {"content-type": "application/x-www-form-urlencoded"})


@pytest.mark.parametrize("status,expected", [("TRADE_SUCCESS", "paid"), ("TRADE_FINISHED", "paid"),
                                           ("WAIT_BUYER_PAY", None), ("TRADE_CLOSED", "cancelled")])
async def test_only_confirmed_alipay_trade_statuses_can_credit(alipay, status, expected):
    receipt = await alipay.adapter.verify_webhook(alipay.notify(trade_status=status),
        {"content-type": "application/x-www-form-urlencoded; charset=UTF-8"})
    assert (receipt.status if receipt is not None else None) == expected
    if receipt:
        assert receipt.amount_fen == 10


async def test_query_verifies_exact_raw_json_and_identity(alipay, monkeypatch):
    body = alipay.response(subject="中文 + 测试")

    def handler(request):
        assert request.url.scheme == "https" and request.url.host == "openapi.alipay.com"
        assert request.url.path == "/gateway.do"
        common = dict(request.url.params)
        assert common["charset"] == "utf-8"
        assert request.headers["content-type"] == "application/x-www-form-urlencoded;charset=utf-8"
        form = dict(parse_qsl(request.content.decode()))
        assert set(form) == {"biz_content"}
        params = {**common, **form}
        verify_request(alipay, params)
        assert params["method"] == "alipay.trade.query"
        assert json.loads(params["biz_content"]) == {"out_trade_no": "pay-test"}
        return httpx.Response(200, content=body)

    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    assert (await alipay.adapter.query_payment("pay-test")).amount_fen == 10
    for body in [alipay.response(out_trade_no="other"), alipay.response(seller_id="2088000000000002"),
                 alipay.response().replace('"0.10"', '"0.20"'), alipay.response().replace('"sign":', '"sign":"bad", "sign":')]:
        with pytest.raises(BillingError):
            await alipay.adapter.query_payment("pay-test")
    body = alipay.response(trade_status="WAIT_BUYER_PAY")
    assert await alipay.adapter.query_payment("pay-test") is None
    body = alipay.response(trade_status="TRADE_CLOSED")
    assert (await alipay.adapter.query_payment("pay-test")).status == "cancelled"
    body = alipay.response(code="40004", sub_code="ACQ.TRADE_NOT_EXIST")
    assert await alipay.adapter.query_payment("pay-test") == TradeNotCreated("pay-test")
    body = alipay.response(code="40004", sub_code="ACQ.ACCESS_FORBIDDEN")
    with pytest.raises(BillingError):
        await alipay.adapter.query_payment("pay-test")


@pytest.fixture
async def payer(monkeypatch):
    monkeypatch.setenv("BILLING_PLANS_FILE", str(Path(__file__).parents[2] / "billing/plans.payment-test.json"))
    user = await PgUserRepo().create(id=ascending("test_user"), username="alipay_" + uuid4().hex,
        email=uuid4().hex + "@example.test", password_hash="unused")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": user["id"]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield SimpleNamespace(user=user, app=app, client=client)


async def subscribe(payer, plan="pro"):
    return await create_order(workspace_id=payer.user["default_workspace_id"], user_id=payer.user["id"],
        provider_name="alipay", request_key=uuid4().hex, kind="subscription", plan_id=plan, cycle="monthly")


async def test_native_webhook_returns_plain_success_only_after_exact_once_credit(alipay, payer):
    order = await subscribe(payer)
    assert order["amount_fen"] == 10
    callback = "/api/billing/webhooks/alipay"
    headers = {"content-type": "application/x-www-form-urlencoded"}
    send = lambda **changes: payer.client.post(callback, content=alipay.notify(order["id"], **changes), headers=headers)
    assert (await send(total_amount="0.20")).status_code == 409
    assert (await payer.client.post(callback, content=alipay.notify(order["id"]).replace(b"0.10", b"0.20"), headers=headers)).status_code == 401
    async with get_db_session() as db:
        assert (await db.get(PaymentOrder, order["id"])).status == "pending"
    for _ in range(2):
        result = await send()
        assert result.status_code == 200 and result.text == "success"
        assert result.headers["content-type"].startswith("text/plain")
    assert (await send(trade_status="TRADE_FINISHED")).text == "success"
    assert (await send(trade_no="another-trade")).status_code == 409
    next_order = await subscribe(payer, "max")
    assert next_order["amount_fen"] == 20
    assert (await payer.client.post(callback, content=alipay.notify(next_order["id"], total_amount="0.20"), headers=headers)).status_code == 409
    async with get_db_session() as db:
        ws = payer.user["default_workspace_id"]
        assert (await db.get(CreditBalance, ws)).balance == 280
        assert await db.scalar(select(func.count()).select_from(CreditLedger).where(CreditLedger.workspace_id == ws)) == 1
    assert (await payer.client.get("/api/billing/subscription")).json()["plan_id"] == "pro"


async def test_native_app_checkout_endpoint_returns_ephemeral_sdk_payload(alipay, payer):
    order = await subscribe(payer)
    providers = (await payer.client.get("/api/billing/providers")).json()["items"]
    assert providers[0]["supports_app_checkout"] is True
    result = (await payer.client.post(f"/api/billing/orders/{order['id']}/app-checkout")).json()
    assert result["provider"] == "alipay" and result["order"]["id"] == order["id"]
    params = dict(parse_qsl(result["sdk_payload"]))
    verify_request(alipay, params)
    assert params["method"] == "alipay.trade.app.pay"
    async with get_db_session() as db:
        saved = await db.get(PaymentOrder, order["id"])
        assert saved.provider_order_id == order["id"]
        assert saved.checkout_url == order["checkout_url"]


async def test_unpaid_notification_does_not_activate_a_plan(alipay, payer):
    order = await subscribe(payer)
    response = await payer.client.post("/api/billing/webhooks/alipay", content=alipay.notify(order["id"], trade_status="WAIT_BUYER_PAY"),
        headers={"content-type": "application/x-www-form-urlencoded"})
    assert response.text == "success"
    async with get_db_session() as db:
        assert (await db.get(PaymentOrder, order["id"])).status == "pending"
        assert (await db.get(CreditBalance, payer.user["default_workspace_id"])).balance == 0


@pytest.mark.parametrize("confirmation_mode", ["callback", "query"])
async def test_recovery_query_settles_once_and_rejects_other_payers(alipay, payer, monkeypatch, confirmation_mode):
    from billing import providers
    alipay.adapter.confirmation_mode = confirmation_mode
    if confirmation_mode == "query":
        monkeypatch.delenv("PAYMENT_PUBLIC_BASE_URL")
    monkeypatch.setattr(providers, "_registered", {"alipay": alipay.adapter})
    monkeypatch.setenv("PAYMENT_PROVIDERS_JSON", "{}")
    order = await subscribe(payer)
    calls = []

    async def query(order_id):
        calls.append(order_id)
        return await alipay.adapter.verify_webhook(alipay.notify(order_id),
            {"content-type": "application/x-www-form-urlencoded"})

    monkeypatch.setattr(alipay.adapter, "query_payment", query)
    route = f"/api/billing/orders/{order['id']}/refresh"
    stranger = await PgUserRepo().create(id=ascending("stranger"), username="alipay_other_" + uuid4().hex,
        email=uuid4().hex + "@example.test", password_hash="unused")
    payer.app.dependency_overrides[get_current_user] = lambda: {"user_id": stranger["id"]}
    assert (await payer.client.post(route)).status_code == 404
    assert calls == []
    payer.app.dependency_overrides[get_current_user] = lambda: {"user_id": payer.user["id"]}
    for _ in range(2):
        assert (await payer.client.post(route)).json()["status"] == "paid"
    assert calls == [order["id"]]
    async with get_db_session() as db:
        assert (await db.get(CreditBalance, payer.user["default_workspace_id"])).balance == 280


async def test_checkout_refresh_keeps_original_order_and_price_snapshot(alipay, payer, monkeypatch):
    from billing import providers
    from unittest.mock import AsyncMock
    monkeypatch.setattr(alipay.adapter, "query_payment", AsyncMock(return_value=None))
    monkeypatch.setattr(providers, "_registered", {"alipay": alipay.adapter})
    monkeypatch.setenv("PAYMENT_PROVIDERS_JSON", "{}")
    order = await subscribe(payer)
    alipay.adapter.subject = "bossip 更新链接"
    response = await payer.client.post(f"/api/billing/orders/{order['id']}/checkout")
    assert response.status_code == 200
    fresh = response.json()
    assert fresh["id"] == order["id"] and fresh["amount_fen"] == 10
    assert fresh["checkout_url"] != order["checkout_url"]
    assert json.loads(dict(parse_qsl(urlsplit(fresh["checkout_url"]).query))["biz_content"])["total_amount"] == "0.10"


async def test_query_mode_needs_no_public_url_and_unpaid_order_cannot_activate_plan(alipay, payer, monkeypatch):
    config = {**alipay.config, "confirmation_mode": "query"}
    monkeypatch.setenv("PAYMENT_PROVIDERS_JSON", json.dumps({"alipay": config}))
    monkeypatch.delenv("PAYMENT_PUBLIC_BASE_URL")
    assert callback_url("alipay") is None
    provider = (await payer.client.get("/api/billing/providers")).json()["items"][0]
    assert provider["confirmation_mode"] == "query" and provider["supports_status_query"]
    order = await subscribe(payer)
    params = dict(parse_qsl(urlsplit(order["checkout_url"]).query))
    verify_request(alipay, params)
    assert "notify_url" not in params and "return_url" not in params

    async def query(self, order_id):
        assert order_id == order["id"]
        return None

    monkeypatch.setattr(AlipayPaymentProvider, "query_payment", query)
    assert (await payer.client.post(f"/api/billing/orders/{order['id']}/refresh")).json()["status"] == "pending"
    async with get_db_session() as db:
        assert (await db.get(CreditBalance, payer.user["default_workspace_id"])).balance == 0
        assert (await db.get(PaymentOrder, order["id"])).status == "pending"


async def test_callback_mode_still_requires_public_url(alipay, monkeypatch):
    monkeypatch.delenv("PAYMENT_PUBLIC_BASE_URL")
    with pytest.raises(BillingError, match="HTTPS"):
        callback_url("alipay")
    with pytest.raises(BillingError, match="HTTPS"):
        await alipay.adapter.create_checkout(order_id="pay-test", amount_fen=10, callback_url=None)
    with pytest.raises(ValueError, match="confirmation mode"):
        AlipayPaymentProvider({**alipay.config, "confirmation_mode": "unverified"})


async def test_closed_order_cannot_resume_and_paid_receipt_wins_over_delayed_close(alipay, payer):
    order = await subscribe(payer)
    headers = {"content-type": "application/x-www-form-urlencoded"}
    route = "/api/billing/webhooks/alipay"
    wrong = alipay.notify(order["id"], trade_status="TRADE_CLOSED", total_amount="0.20")
    assert (await payer.client.post(route, content=wrong, headers=headers)).status_code == 409
    closed = alipay.notify(order["id"], trade_status="TRADE_CLOSED")
    for _ in range(2):
        assert (await payer.client.post(route, content=closed, headers=headers)).text == "success"
    view = (await payer.client.get(f"/api/billing/orders/{order['id']}")).json()
    assert view["status"] == "cancelled" and view["checkout_url"] is None
    assert (await payer.client.post(f"/api/billing/orders/{order['id']}/checkout")).status_code == 409
    async with get_db_session() as db:
        assert (await db.get(CreditBalance, payer.user["default_workspace_id"])).balance == 0
        assert await db.scalar(select(func.count()).select_from(CreditLedger).where(CreditLedger.reference_id == order["id"])) == 0
    # Authenticated payment evidence wins if notifications arrive out of order.
    assert (await payer.client.post(route, content=alipay.notify(order["id"]), headers=headers)).text == "success"
    assert (await payer.client.post(route, content=closed, headers=headers)).text == "success"
    view = (await payer.client.get(f"/api/billing/orders/{order['id']}")).json()
    assert view["status"] == "paid" and view["checkout_url"] is None
    async with get_db_session() as db:
        assert (await db.get(CreditBalance, payer.user["default_workspace_id"])).balance == 280


async def test_closed_query_updates_order_status_without_crediting(alipay, payer, monkeypatch):
    order = await subscribe(payer)

    async def query(self, order_id):
        return await self.verify_webhook(alipay.notify(order_id, trade_status="TRADE_CLOSED"),
            {"content-type": "application/x-www-form-urlencoded"})

    monkeypatch.setattr(AlipayPaymentProvider, "query_payment", query)
    result = await payer.client.post(f"/api/billing/orders/{order['id']}/refresh")
    assert result.json()["status"] == "cancelled" and result.json()["checkout_url"] is None
    async with get_db_session() as db:
        assert (await db.get(CreditBalance, payer.user["default_workspace_id"])).balance == 0


async def test_order_filters_combine_status_channel_id_and_local_dates_with_pagination(alipay, payer):
    from datetime import datetime
    specs = [
        ("2026-09-04T15:59:59+00:00", "pending"),
        ("2026-09-04T16:00:00+00:00", "cancelled"),
        ("2026-09-05T03:00:00+00:00", "paid"),
        ("2026-09-05T15:59:59+00:00", "pending"),
        ("2026-09-05T16:00:00+00:00", "pending"),
    ]
    orders = []
    for timestamp, status in specs:
        order = {"id": ascending("pay")}
        orders.append(order)
        async with get_db_session() as db:
            db.add(PaymentOrder(id=order["id"], workspace_id=payer.user["default_workspace_id"],
                user_id=payer.user["id"], request_key=uuid4().hex, provider="alipay", kind="topup",
                amount_fen=10, currency="CNY", credits=1, created_at=datetime.fromisoformat(timestamp), status=status))
    filters = {"date_from": "2026-09-05", "date_to": "2026-09-05", "tz": "Asia/Shanghai"}
    first = (await payer.client.get("/api/billing/orders", params={**filters, "page_size": 2})).json()
    second = (await payer.client.get("/api/billing/orders", params={**filters, "page_size": 2, "page": 2})).json()
    assert first["total"] == 3 and first["total_pages"] == 2
    assert [row["id"] for row in first["items"] + second["items"]] == [orders[i]["id"] for i in (3, 2, 1)]
    combined = {**filters, "status": "cancelled", "provider": "alipay", "order_id": orders[1]["id"]}
    selected = (await payer.client.get("/api/billing/orders", params=combined)).json()
    assert selected["total"] == 1 and selected["items"][0]["checkout_url"] is None
    assert (await payer.client.get("/api/billing/orders", params={"provider": "missing"})).json()["total"] == 0
    assert (await payer.client.get("/api/billing/orders", params={"order_id": "%"})).json()["total"] == 0
    for bad in ({"status": "unknown"}, {"date_from": "2026-09-06", "date_to": "2026-09-05"}, {"tz": "invalid"}):
        assert (await payer.client.get("/api/billing/orders", params=bad)).status_code == 422

async def test_close_distinguishes_uncreated_trades_and_rejects_tampered_responses(alipay, monkeypatch):
    body = alipay.response(method="close")
    def handler(request):
        params = {**dict(request.url.params), **dict(parse_qsl(request.content.decode()))}
        verify_request(alipay, params)
        assert params["method"] == "alipay.trade.close"
        assert json.loads(params["biz_content"]) == {"out_trade_no": "pay-test"}
        return httpx.Response(200, content=body)
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    receipt = await alipay.adapter.close_payment("pay-test", 10)
    assert receipt.status == "cancelled" and receipt.amount_fen == 10
    for body in [
        alipay.response(method="close", out_trade_no="another-order"),
        alipay.response(method="close", seller_id="2088000000000002"),
        alipay.response(method="close").replace('"10000"', '"20000"'),
        alipay.response(method="close", code="40004", sub_code="ACQ.TRADE_NOT_EXIST", out_trade_no="another-order"),
        alipay.response(),  # a correctly signed response to a different API
    ]:
        with pytest.raises(BillingError):
            await alipay.adapter.close_payment("pay-test", 10)
    body = alipay.response(method="close", code="40004", sub_code="ACQ.TRADE_NOT_EXIST")
    assert await alipay.adapter.close_payment("pay-test", 10) == TradeNotCreated("pay-test")


@pytest.mark.parametrize("outcome", ["cancelled", "paid_before_close", "paid_during_close", "close_timeout", "wrong_order"])
async def test_cancel_checks_actual_payment_and_never_loses_a_racing_receipt(alipay, payer, monkeypatch, outcome):
    from unittest.mock import AsyncMock
    from billing.providers import CancelledReceipt, PaidReceipt
    order = await subscribe(payer)
    paid = PaidReceipt(order_id=order["id"], payment_id="confirmed-" + order["id"], amount_fen=10, currency="CNY", status="paid")
    closed = CancelledReceipt(order_id=order["id"], payment_id="closed-trade", amount_fen=10, currency="CNY", status="cancelled")
    calls = []
    async def query(self, order_id):
        assert order_id == order["id"]
        calls.append(order_id)
        return paid if outcome == "paid_before_close" or (outcome == "paid_during_close" and len(calls) > 1) else None
    async def close(self, order_id, amount):
        assert order_id == order["id"] and amount == 10
        if outcome in {"paid_during_close", "close_timeout"}:
            raise BillingError("PAYMENT_CANCEL_FAILED", "Timeout")
        return closed.model_copy(update={"order_id": "unrelated"}) if outcome == "wrong_order" else closed
    close_mock = AsyncMock(side_effect=close)
    monkeypatch.setattr(AlipayPaymentProvider, "query_payment", query)
    # Bind through a real function so the mock can observe provider self.
    async def cancel(self, order_id, amount):
        return await close_mock(self, order_id, amount)
    monkeypatch.setattr(AlipayPaymentProvider, "close_payment", cancel)
    route = f"/api/billing/orders/{order['id']}/cancel"
    result = await payer.client.post(route)
    expected = "paid" if outcome.startswith("paid") else "cancelled" if outcome == "cancelled" else "pending"
    assert result.status_code == (200 if expected != "pending" else 422 if outcome == "wrong_order" else 502)
    view = (await payer.client.get(f"/api/billing/orders/{order['id']}")).json()
    assert view["status"] == expected
    if expected != "pending":
        assert view["checkout_url"] is None
        assert (await payer.client.post(route)).json()["status"] == expected
    assert close_mock.await_count == (0 if outcome == "paid_before_close" else 1)
    async with get_db_session() as db:
        assert (await db.get(CreditBalance, payer.user["default_workspace_id"])).balance == (280 if expected == "paid" else 0)


async def test_continue_checks_gateway_before_returning_a_checkout(alipay, payer, monkeypatch):
    order = await subscribe(payer)
    async def query(self, order_id):
        return await self.verify_webhook(alipay.notify(order_id), {"content-type": "application/x-www-form-urlencoded"})
    monkeypatch.setattr(AlipayPaymentProvider, "query_payment", query)
    result = await payer.client.post(f"/api/billing/orders/{order['id']}/checkout")
    assert result.status_code == 200
    assert result.json()["status"] == "paid" and result.json()["checkout_url"] is None


async def test_cancel_only_original_payer_can_close_order(alipay, payer, monkeypatch):
    from unittest.mock import AsyncMock
    order = await subscribe(payer)
    close = AsyncMock()
    monkeypatch.setattr(AlipayPaymentProvider, "close_payment", close)
    stranger = await PgUserRepo().create(id=ascending("stranger"), username=uuid4().hex, password_hash="unused")
    payer.app.dependency_overrides[get_current_user] = lambda: {"user_id": stranger["id"]}
    assert (await payer.client.post(f"/api/billing/orders/{order['id']}/cancel")).status_code == 404
    close.assert_not_awaited()


async def test_realistic_uncreated_legacy_order_can_cancel_without_a_gateway_trade(alipay, payer, monkeypatch):
    # Real production query/close failures contain no trade_no or amount.
    order = await subscribe(payer)
    requests = []
    def handler(request):
        params = {**dict(request.url.params), **dict(parse_qsl(request.content.decode()))}
        verify_request(alipay, params)
        method = params["method"]
        assert json.loads(params["biz_content"])["out_trade_no"] == order["id"]
        requests.append(method)
        fields = {"code": "40004", "msg": "Business Failed", "sub_code": "ACQ.TRADE_NOT_EXIST", "sub_msg": "交易不存在"}
        if method == "alipay.trade.query":
            fields["out_trade_no"] = order["id"]
        raw = json.dumps(fields, ensure_ascii=False, separators=(",", ":"))
        body = "{" + json.dumps(method.replace(".", "_") + "_response") + ":" + raw + ',"sign":' + json.dumps(alipay.sign(raw.encode())) + "}"
        return httpx.Response(200, content=body)
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    refresh = f"/api/billing/orders/{order['id']}/refresh"
    assert (await payer.client.post(refresh)).json()["status"] == "pending"
    cancel = f"/api/billing/orders/{order['id']}/cancel"
    result = await payer.client.post(cancel)
    assert result.status_code == 200, result.text
    view = result.json()
    assert view["status"] == "cancelled" and view["checkout_url"] is None and view["cancelled_at"]
    assert view["cancellation_reason"] == "trade_not_created" and view["reconcile_required"] is True
    assert requests.count("alipay.trade.close") == 1
    assert (await payer.client.post(cancel)).json()["status"] == "cancelled"
    assert requests.count("alipay.trade.close") == 1
    assert (await payer.client.post(f"/api/billing/orders/{order['id']}/checkout")).status_code == 409
    listing = (await payer.client.get("/api/billing/orders", params={"status": "cancelled"})).json()
    assert listing["items"][0]["id"] == order["id"]
    assert (await payer.client.get("/api/billing/orders", params={"status": "pending"})).json()["total"] == 0
    async with get_db_session() as db:
        assert (await db.get(CreditBalance, payer.user["default_workspace_id"])).balance == 0
        assert await db.scalar(select(func.count()).select_from(CreditLedger).where(CreditLedger.reference_id == order["id"])) == 0


@pytest.mark.parametrize("late_status", ["paid", "waiting", "paid_during_close", "unavailable"])
async def test_cancelled_uncreated_orders_keep_reconciling_late_payments(alipay, payer, monkeypatch, late_status):
    from billing.providers import PaidReceipt, CancelledReceipt
    order = await subscribe(payer)
    state = ["uncreated"]
    paid = PaidReceipt(order_id=order["id"], payment_id="late-" + order["id"], amount_fen=10, currency="CNY", status="paid")
    closed = CancelledReceipt(order_id=order["id"], payment_id="close-" + order["id"], amount_fen=10, currency="CNY", status="cancelled")
    async def query(self, order_id):
        if state[0] == "paid": return paid
        if state[0] in {"waiting", "paid_during_close", "unavailable"}: return None
        return TradeNotCreated(order_id)
    async def close(self, order_id, amount):
        if state[0] == "paid_during_close":
            state[0] = "paid"
            raise BillingError("PAYMENT_CANCEL_FAILED", "Payment just completed")
        if state[0] == "unavailable":
            raise BillingError("PAYMENT_CANCEL_FAILED", "Network unavailable")
        return TradeNotCreated(order_id) if state[0] == "uncreated" else closed
    monkeypatch.setattr(AlipayPaymentProvider, "query_payment", query)
    monkeypatch.setattr(AlipayPaymentProvider, "close_payment", close)
    assert (await payer.client.post(f"/api/billing/orders/{order['id']}/cancel")).json()["reconcile_required"]
    state[0] = late_status
    result = await payer.client.post(f"/api/billing/orders/{order['id']}/refresh")
    is_paid = late_status.startswith("paid")
    assert result.status_code == (502 if late_status == "unavailable" else 200)
    view = (await payer.client.get(f"/api/billing/orders/{order['id']}")).json()
    assert view["status"] == ("paid" if is_paid else "cancelled")
    assert view["reconcile_required"] is (late_status == "unavailable")
    if is_paid:
        # Subsequent refresh/cancel must not issue another credit.
        await payer.client.post(f"/api/billing/orders/{order['id']}/cancel")
        await payer.client.post(f"/api/billing/orders/{order['id']}/refresh")
    async with get_db_session() as db:
        assert (await db.get(CreditBalance, payer.user["default_workspace_id"])).balance == (280 if is_paid else 0)
