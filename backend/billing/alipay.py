"""Alipay direct-merchant PC website payment (RSA2 public-key mode).

Only signed notifications / signed trade queries can confirm a payment. The
browser return URL is navigation, never evidence that an order was paid.
"""
from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit
from zoneinfo import ZoneInfo

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from billing.providers import Checkout, PaidReceipt, CancelledReceipt, VerifiedReceipt, TradeNotCreated
from billing.service import BillingError

GATEWAYS = {
    "production": "https://openapi.alipay.com/gateway.do",
    "sandbox": "https://openapi-sandbox.dl.alipaydev.com/gateway.do",
}


def canonical(params: Mapping[str, str], *, notification: bool = False) -> bytes:
    excluded = {"sign", "sign_type"} if notification else {"sign"}
    return "&".join(f"{key}={value}" for key, value in sorted(params.items())
                    if key not in excluded and value != "").encode("utf-8")


def _key_bytes(config: dict, name: str, label: str) -> bytes:
    # Paths keep private keys out of JSON/environment dumps. Inline PEM remains
    # useful for secret managers. Never log either representation.
    value = Path(config[name + "_file"]).expanduser().read_bytes() if config.get(name + "_file") else config[name].encode()
    if b"-----BEGIN" not in value:
        value = b"-----BEGIN " + label.encode() + b"-----\n" + value.strip() + b"\n-----END " + label.encode() + b"-----\n"
    return value


def _https_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.fragment or len(value) > 256 or any(ord(char) < 32 for char in value)):
        raise ValueError("Alipay URLs must be HTTPS, without credentials or fragments, and at most 256 characters")
    return value


def _amount_fen(value: object) -> int:
    # Decimal avoids binary rounding; reject exponent notation and fractions of
    # a fen instead of rounding a receipt to match a different order amount.
    if not isinstance(value, (str, Decimal, int)) or isinstance(value, bool) or not re.fullmatch(r"[0-9]{1,8}(?:\.[0-9]{1,2})?", str(value)):
        raise BillingError("PAYMENT_INVALID_RECEIPT", "Invalid Alipay amount")
    amount = int(Decimal(str(value)) * 100)
    if not 0 < amount <= 100_000_000:
        raise BillingError("PAYMENT_INVALID_RECEIPT", "Invalid Alipay amount")
    return amount


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


class AlipayPaymentProvider:
    webhook_acknowledgement = "success"
    refresh_checkout = True

    def __init__(self, config: dict):
        self.display_name = config.get("display_name", "支付宝")
        self.app_id = str(config["app_id"])
        self.seller_id = str(config["seller_id"])
        if not re.fullmatch(r"[0-9]{16}", self.app_id) or not re.fullmatch(r"2088[0-9]{12}", self.seller_id):
            raise ValueError("Alipay requires an app ID and the merchant seller ID (PID)")
        self.gateway = GATEWAYS[config.get("environment", "production")]
        self.confirmation_mode = config.get("confirmation_mode", "callback")
        if self.confirmation_mode not in {"callback", "query"}:
            raise ValueError("Unsupported Alipay payment confirmation mode")
        self.return_url = _https_url(config["return_url"]) if config.get("return_url") else None
        self.subject = config.get("subject", "bossip 订购")
        if not isinstance(self.subject, str) or not 1 <= len(self.subject.encode()) <= 64 or any(c in self.subject for c in "\r\n"):
            raise ValueError("Invalid Alipay order subject")
        self.private_key = serialization.load_pem_private_key(_key_bytes(config, "private_key", "PRIVATE KEY"), password=None)
        self.public_key = serialization.load_pem_public_key(_key_bytes(config, "alipay_public_key", "PUBLIC KEY"))
        if (not isinstance(self.private_key, rsa.RSAPrivateKey) or self.private_key.key_size < 2048
                or not isinstance(self.public_key, rsa.RSAPublicKey) or self.public_key.key_size < 2048):
            raise ValueError("Alipay RSA2 requires RSA keys of at least 2048 bits")

    def _request(self, method: str, biz: dict, **extra: str) -> dict[str, str]:
        params = {"app_id": self.app_id, "method": method, "format": "JSON", "charset": "utf-8",
                  "sign_type": "RSA2", "timestamp": datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S"),
                  "version": "1.0", "biz_content": json.dumps(biz, ensure_ascii=False, separators=(",", ":")), **extra}
        params["sign"] = base64.b64encode(self.private_key.sign(canonical(params), padding.PKCS1v15(), hashes.SHA256())).decode()
        return params

    def _verify(self, content: bytes, sign: str) -> None:
        try:
            supplied = base64.b64decode(sign, validate=True)
            self.public_key.verify(supplied, content, padding.PKCS1v15(), hashes.SHA256())
        except (InvalidSignature, ValueError, TypeError) as exc:
            raise BillingError("PAYMENT_INVALID_SIGNATURE", "Invalid Alipay signature") from exc

    async def create_checkout(self, *, order_id: str, amount_fen: int, callback_url: str | None) -> Checkout:
        extra = {}
        if self.confirmation_mode == "callback":
            if not callback_url:
                raise BillingError("PAYMENT_UNAVAILABLE", "Configure an HTTPS Alipay callback URL")
            extra["notify_url"] = _https_url(callback_url)
            extra["return_url"] = _https_url(callback_url.rsplit("/api/billing/", 1)[0] + "/app/billing/orders")
        # Local query confirmation does not publish a callback or a localhost
        # URL. The payer returns to the order and requests a signed trade query.
        if self.return_url:
            extra["return_url"] = self.return_url
        params = self._request("alipay.trade.page.pay", {
            "out_trade_no": order_id, "total_amount": f"{Decimal(amount_fen) / 100:.2f}",
            "subject": self.subject, "product_code": "FAST_INSTANT_TRADE_PAY",
        }, **extra)
        url = self.gateway + "?" + urlencode(params)
        if len(url) > 2048:
            raise BillingError("PAYMENT_INVALID_CHECKOUT", "Alipay checkout URL exceeds the supported length")
        # Alipay deduplicates a merchant's out_trade_no. Never invent a new order
        # on timeout/retry, including while its first notification is in flight.
        return Checkout(url, order_id)

    def _receipt(self, params: Mapping) -> VerifiedReceipt | None:
        status = params.get("trade_status")
        if status == "WAIT_BUYER_PAY":
            return None
        if status not in {"TRADE_SUCCESS", "TRADE_FINISHED", "TRADE_CLOSED"}:
            raise BillingError("PAYMENT_INVALID_RECEIPT", "Unknown Alipay trade status")
        receipt_type = CancelledReceipt if status == "TRADE_CLOSED" else PaidReceipt
        return receipt_type(order_id=params.get("out_trade_no"), payment_id=params.get("trade_no"),
            amount_fen=_amount_fen(params.get("total_amount")), currency="CNY",
            status="cancelled" if status == "TRADE_CLOSED" else "paid")

    async def verify_webhook(self, body: bytes, headers: Mapping[str, str]) -> VerifiedReceipt | None:
        if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
            raise BillingError("PAYMENT_INVALID_RECEIPT", "Alipay notifications must be form encoded")
        try:
            encoded = body.decode("utf-8", errors="strict")
            if re.search(r"%(?![0-9a-fA-F]{2})", encoded):
                raise ValueError("Invalid percent encoding")
            params = _unique_object(parse_qsl(encoded, keep_blank_values=True, strict_parsing=True,
                                             encoding="utf-8", errors="strict", max_num_fields=128))
        except ValueError as exc:
            raise BillingError("PAYMENT_INVALID_RECEIPT", "Malformed Alipay notification") from exc
        if params.get("sign_type") != "RSA2" or params.get("charset", "utf-8").lower() != "utf-8":
            raise BillingError("PAYMENT_INVALID_SIGNATURE", "Alipay notification must use RSA2 / UTF-8")
        self._verify(canonical(params, notification=True), params.get("sign", ""))
        if params.get("app_id") != self.app_id or params.get("seller_id") != self.seller_id:
            raise BillingError("PAYMENT_INVALID_RECEIPT", "Alipay application or seller differs from configuration")
        if params.get("notify_type") != "trade_status_sync":
            raise BillingError("PAYMENT_INVALID_RECEIPT", "Unsupported Alipay notification type")
        # Do not impose a five-minute timestamp window: Alipay retries delayed
        # notifications. The unique receipt + order ledger enforce idempotency.
        return self._receipt(params)

    def _query_response(self, body: str, key: str = "alipay_trade_query_response") -> dict:
        try:
            decoder = json.JSONDecoder(object_pairs_hook=_unique_object, parse_float=Decimal)
            envelope = decoder.decode(body)
            if not isinstance(envelope, dict) or not isinstance(envelope.get(key), dict):
                raise ValueError("Missing response envelope")
            # Verify the exact original JSON object, preserving spaces, escaped
            # Unicode and numeric formatting. Re-serializing would change it.
            cursor = body.index("{") + 1
            while True:
                cursor += len(body[cursor:]) - len(body[cursor:].lstrip())
                name, cursor = decoder.raw_decode(body, cursor)
                cursor = body.index(":", cursor) + 1
                cursor += len(body[cursor:]) - len(body[cursor:].lstrip())
                start = cursor
                _, cursor = decoder.raw_decode(body, cursor)
                if name == key:
                    self._verify(body[start:cursor].encode("utf-8"), envelope.get("sign", ""))
                    return envelope[key]
                cursor = body.index(",", cursor) + 1
        except (ValueError, TypeError) as exc:
            raise BillingError("PAYMENT_QUERY_FAILED", "Invalid Alipay query response") from exc

    async def _trade_request(self, method: str, order_id: str) -> dict:
        params = self._request(method, {"out_trade_no": order_id})
        # The gateway reads the response charset from the URL's common params.
        # Match the official SDK: only biz_content belongs in the POST body.
        body = {"biz_content": params.pop("biz_content")}
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                response = await client.post(self.gateway, params=params, data=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"})
                response.raise_for_status()
            if len(response.content) > 65_536:
                raise ValueError("Oversized response")
            data = self._query_response(response.content.decode("utf-8"), method.replace(".", "_") + "_response")
        except (httpx.HTTPError, ValueError) as exc:
            raise BillingError("PAYMENT_QUERY_FAILED", "Unable to query Alipay payment status") from exc
        if data.get("out_trade_no", order_id) != order_id:
            raise BillingError("PAYMENT_INVALID_RECEIPT", "Alipay returned a different order")
        if data.get("app_id", self.app_id) != self.app_id or data.get("seller_id", self.seller_id) != self.seller_id:
            raise BillingError("PAYMENT_INVALID_RECEIPT", "Alipay returned a different merchant")
        if data.get("code") == "10000":
            if data.get("out_trade_no") != order_id:
                raise BillingError("PAYMENT_INVALID_RECEIPT", "Alipay returned a different order")
        return data

    async def query_payment(self, order_id: str) -> VerifiedReceipt | TradeNotCreated | None:
        data = await self._trade_request("alipay.trade.query", order_id)
        if data.get("code") != "10000":
            if data.get("sub_code") == "ACQ.TRADE_NOT_EXIST":
                return TradeNotCreated(order_id)
            raise BillingError("PAYMENT_QUERY_FAILED", "Alipay could not query this order")
        return self._receipt(data)

    async def close_payment(self, order_id: str, amount_fen: int) -> CancelledReceipt | TradeNotCreated:
        data = await self._trade_request("alipay.trade.close", order_id)
        if data.get("code") != "10000":
            if data.get("sub_code") == "ACQ.TRADE_NOT_EXIST":
                # No upstream transaction exists to close. The merchant can
                # cancel its order, but must still reconcile older issued URLs.
                return TradeNotCreated(order_id)
            raise BillingError("PAYMENT_CANCEL_FAILED", "支付宝尚未确认关单，请稍后重试或查询支付状态")
        return CancelledReceipt(order_id=order_id, payment_id=data.get("trade_no"),
            amount_fen=amount_fen, currency="CNY", status="cancelled")
