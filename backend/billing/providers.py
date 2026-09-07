"""Replaceable payment boundary. Only verified receipts may reach the ledger.

The HTTP adapter lets an external payment service bridge any vendor SDK. A native
adapter can implement PaymentProvider and be registered without changing accounting.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Mapping, Protocol
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from billing.service import BillingError


class PaymentReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    order_id: str = Field(min_length=1, max_length=64)
    payment_id: str = Field(min_length=1, max_length=160)
    amount_fen: int = Field(gt=0, le=100_000_000)
    currency: str = Field(pattern="^CNY$")


class PaidReceipt(PaymentReceipt):
    status: str = Field(pattern="^paid$")


class CancelledReceipt(PaymentReceipt):
    status: str = Field(pattern="^cancelled$")


VerifiedReceipt = PaidReceipt | CancelledReceipt


@dataclass(frozen=True)
class TradeNotCreated:
    """Signed gateway evidence of no trade yet, not a closed-trade receipt."""
    order_id: str


@dataclass(frozen=True)
class Checkout:
    url: str
    provider_order_id: str


@dataclass(frozen=True)
class AppCheckout:
    """Opaque payload signed by the server for a provider's native SDK."""
    payload: str
    provider_order_id: str


class CheckoutResponse(BaseModel):
    model_config = ConfigDict(strict=True)
    checkout_url: str = Field(min_length=1, max_length=2048)
    provider_order_id: str = Field(min_length=1, max_length=160)


class PaymentProvider(Protocol):
    display_name: str

    async def create_checkout(self, *, order_id: str, amount_fen: int, callback_url: str | None) -> Checkout: ...
    async def verify_webhook(self, body: bytes, headers: Mapping[str, str]) -> VerifiedReceipt | None: ...


def signature(secret: str, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


class HttpPaymentProvider:
    """Version 1 signed JSON contract, with provider-side order-id idempotency."""
    def __init__(self, config: dict):
        self.base_url = config["base_url"].rstrip("/")
        self.api_key = config["api_key"]
        self.secret = config["webhook_secret"]
        self.display_name = config["display_name"]
        self.checkout_hosts = set(config["checkout_hosts"])
        if urlsplit(self.base_url).scheme != "https" or len(self.secret) < 32 or not self.checkout_hosts:
            raise ValueError("Payment provider requires HTTPS, allowed checkout hosts and a 32+ character secret")

    async def create_checkout(self, *, order_id: str, amount_fen: int, callback_url: str | None) -> Checkout:
        if not callback_url:
            raise BillingError("PAYMENT_UNAVAILABLE", "The HTTP payment adapter requires a callback URL")
        body = json.dumps({"version": 1, "order_id": order_id, "amount_fen": amount_fen,
                           "currency": "CNY", "callback_url": callback_url}, separators=(",", ":")).encode()
        timestamp = str(int(time.time()))
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            response = await client.post(self.base_url + "/checkouts", content=body, headers={
                "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                "Idempotency-Key": order_id, "X-Payment-Timestamp": timestamp,
                "X-Payment-Signature": signature(self.secret, timestamp, body)})
            response.raise_for_status()
            data = response.json()
        try:
            checkout = CheckoutResponse.model_validate(data)
        except ValueError as exc:
            raise BillingError("PAYMENT_INVALID_CHECKOUT", "Invalid provider checkout") from exc
        url = checkout.checkout_url
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname not in self.checkout_hosts or parsed.username or parsed.password:
            raise BillingError("PAYMENT_INVALID_CHECKOUT", "Provider returned an unapproved checkout URL")
        return Checkout(url, checkout.provider_order_id)

    async def verify_webhook(self, body: bytes, headers: Mapping[str, str]) -> VerifiedReceipt:
        timestamp = headers.get("x-payment-timestamp", "")
        supplied = headers.get("x-payment-signature", "")
        if not re.fullmatch(r"[0-9]{1,12}", timestamp) or abs(time.time() - int(timestamp)) > 300:
            raise BillingError("PAYMENT_INVALID_SIGNATURE", "Expired or missing webhook timestamp")
        if not re.fullmatch(r"[0-9a-f]{64}", supplied) or not hmac.compare_digest(signature(self.secret, timestamp, body), supplied):
            raise BillingError("PAYMENT_INVALID_SIGNATURE", "Invalid webhook signature")
        # Parse only AFTER authenticating the exact raw body.
        return TypeAdapter(VerifiedReceipt).validate_json(body)


_registered: dict[str, PaymentProvider] = {}


def register_provider(name: str, provider: PaymentProvider) -> None:
    if not re.fullmatch(r"[a-z0-9_-]{1,64}", name):
        raise ValueError("Invalid provider name")
    _registered[name] = provider


def providers() -> dict[str, PaymentProvider]:
    result = dict(_registered)
    for name, config in json.loads(os.environ.get("PAYMENT_PROVIDERS_JSON", "{}")).items():
        if not re.fullmatch(r"[a-z0-9_-]{1,64}", name):
            raise ValueError("Unsupported payment adapter configuration")
        if config.get("kind") == "http":
            result[name] = HttpPaymentProvider(config)
        elif config.get("kind") == "alipay":
            from billing.alipay import AlipayPaymentProvider
            result[name] = AlipayPaymentProvider(config)
        else:
            raise ValueError("Unsupported payment adapter configuration")
    return result


def get_provider(name: str) -> PaymentProvider:
    provider = providers().get(name)
    if provider is None:
        raise BillingError("PAYMENT_UNAVAILABLE", "Payment channel is not configured")
    return provider
