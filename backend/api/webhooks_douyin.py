"""Douyin open-platform webhook receiver.

Unauthenticated by nature; trust comes from `X-Douyin-Signature`
(sha1(client_secret + raw body)). The console's "save URL" step POSTs a
`verify_webhook` event and expects the challenge echoed as JSON text — that is
what lets the URL be saved at all, so it must work before anything else.
"""
import hmac
import json

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from cache import get_cache
from core.config import get_config
from core.log import create_logger
from platforms import service
from platforms.douyin.client import DouyinClient
from platforms.errors import PlatformNotConfigured

log = create_logger("api.webhooks.douyin")

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

_DEDUPE_TTL = 24 * 60 * 60


def _client() -> DouyinClient | None:
    config = get_config()
    try:
        return DouyinClient(config.douyin_client_key, config.douyin_client_secret)
    except PlatformNotConfigured:
        return None


def signature_ok(client: DouyinClient, body: bytes, header: str | None) -> bool:
    if not header:
        return False
    return hmac.compare_digest(client.webhook_signature(body), header.strip().lower())


@router.post("/douyin")
async def douyin_webhook(request: Request):
    client = _client()
    if client is None:
        return Response(status_code=503, content="douyin not configured")
    body = await request.body()
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return Response(status_code=400, content="invalid json")
    if not isinstance(payload, dict):
        return Response(status_code=400, content="invalid payload")

    event = payload.get("event")
    header = request.headers.get("X-Douyin-Signature")
    signed = signature_ok(client, body, header)

    if event == "verify_webhook":
        # The verification POST is the console proving it can reach us. It is
        # signed like every other event, but a missing header here only risks
        # a harmless echo, whereas a strict check would block the URL from ever
        # being saved if the platform's verifier differs from the docs.
        if header and not signed:
            log.warning("douyin verify_webhook with bad signature")
            return Response(status_code=401, content="bad signature")
        challenge = (payload.get("content") or {}).get("challenge")
        return JSONResponse({"challenge": challenge})

    if not signed:
        log.warning("douyin webhook rejected event=%s reason=signature", event)
        return Response(status_code=401, content="bad signature")

    msg_id = request.headers.get("Msg-Id") or request.headers.get("msg-id")
    cache = get_cache()
    if msg_id and cache is not None:
        if await cache.exists(f"douyin:webhook:{msg_id}"):
            return JSONResponse({"ok": True, "duplicate": True})
        await cache.set(f"douyin:webhook:{msg_id}", 1, ttl=_DEDUPE_TTL)

    try:
        changed = await service.handle_douyin_event(payload)
    except Exception:
        # Answer 200 regardless: the platform retries three times and then
        # unsubscribes on persistent failure, which is worse than one lost event.
        log.exception("douyin webhook handling failed event=%s", event)
        changed = False
    return JSONResponse({"ok": True, "handled": changed})
