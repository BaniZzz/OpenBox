"""授权中心: Douyin signing, token ledger, keep-alive, publish and webhook."""
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from cache import set_cache
from cache.memory_cache import MemoryCache
from core.config import get_config
from core.crypto import SecretsConfigError, decrypt_secret, encrypt_secret
from db.base import get_db_session
from db.models.file_asset import FileAsset
from db.models.notification import Notification
from db.models.platform_account import PlatformAccount
from db.models.publish_job import PublishJob
from platforms import service
from platforms.base import Profile, ProviderInfo, TokenGrant
from platforms.douyin.client import DouyinClient, _check
from platforms.douyin.publish import build_share_schema
from platforms.errors import PlatformApiError, PlatformAuthRequired, PlatformError
from platforms.registry import get_provider, set_provider

KEY = "11" * 32
NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


# ── Pure functions ─────────────────────────────────────────────────────────
def test_share_signature_matches_documented_example():
    ticket = "@ml6sqYBGgTKmQNajnKNkaj8yksCAY++adIhlGIqfTiKyvBqOIkzdJ6WRgP+nO+wtVItqKbX4iZ+mFIYkyPJjpQ=="
    assert DouyinClient.sign_share(ticket, "Wm3WZYTPz0wzccnW", "1650941858") == "3f7b739a91a52cb7d85c4f89c5f611fe"


def test_share_schema_carries_signed_fields_and_hashtags():
    schema = build_share_schema(
        client_key="awo",
        ticket="tk",
        video_url="https://bucket.oss-cn-shanghai.aliyuncs.com/publish/x/video.mp4?Expires=1&Signature=a%2Fb",
        share_id="share-1",
        title="测试 标题",
        hashtags=["#装修", "好物", "", "装修"],
        nonce_str="n1",
        timestamp="1700000000",
    )
    parsed = urlparse(schema)
    assert parsed.scheme == "snssdk1128" and parsed.netloc == "openplatform" and parsed.path == "/share"
    # Same wire format as dy_open_util.serialize: sorted keys, encodeURIComponent.
    keys = [part.split("=")[0] for part in parsed.query.split("&")]
    assert keys == sorted(keys)
    assert "title=%E6%B5%8B%E8%AF%95%20%E6%A0%87%E9%A2%98" in schema and "+" not in parsed.query.replace("%2B", "")
    q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    assert q["share_type"] == "h5"
    assert q["client_key"] == "awo"
    assert q["state"] == "share-1"
    assert q["share_to_publish"] == "1"
    assert q["signature"] == DouyinClient.sign_share("tk", "n1", "1700000000")
    assert q["video_path"] == "https://bucket.oss-cn-shanghai.aliyuncs.com/publish/x/video.mp4?Expires=1&Signature=a%2Fb"
    assert json.loads(q["hashtag_list"]) == ["装修", "好物"]
    assert json.loads(q["title_hashtag_list"]) == [{"name": "装修", "start": 5}, {"name": "好物", "start": 5}]
    assert q["title"] == "测试 标题"
    # Defaults are not sent, so an older app never sees an unknown key.
    assert "private_status" not in q and "download_type" not in q and "share_to_type" not in q


def test_share_schema_sends_non_default_switches_only():
    schema = build_share_schema(
        client_key="awo", ticket="tk", video_url="https://x/v.mp4", share_id=None,
        private_status=1, download_type=2, nonce_str="n", timestamp="1700000000",
    )
    q = {k: v[0] for k, v in parse_qs(urlparse(schema).query).items()}
    assert q["private_status"] == "1" and q["download_type"] == "2"
    assert "state" not in q and "title" not in q and "hashtag_list" not in q


def test_response_check_maps_platform_error_codes():
    assert _check({"data": {"error_code": 0, "access_token": "a"}, "message": "success"})["access_token"] == "a"
    with pytest.raises(PlatformAuthRequired):
        _check({"data": {"error_code": 10010, "description": "refresh_token 已过期"}})
    with pytest.raises(PlatformApiError) as exc:
        _check({"data": {"error_code": 10002, "description": "参数错误"}})
    assert exc.value.platform_code == 10002
    with pytest.raises(PlatformAuthRequired):
        _check({"err_no": 28001008, "err_msg": "access_token过期", "data": {}})
    with pytest.raises(PlatformApiError):
        _check({"data": {"share_id": ""}, "extra": {"error_code": 28001007}})


def test_secret_roundtrip_is_bound_to_its_purpose():
    sealed = encrypt_secret("rft.abc", "openbox:platform:douyin:refresh:v1", KEY)
    assert sealed.startswith("v1:")
    assert decrypt_secret(sealed, "openbox:platform:douyin:refresh:v1", KEY) == "rft.abc"
    with pytest.raises(SecretsConfigError):
        decrypt_secret(sealed, "openbox:platform:douyin:access:v1", KEY)


def test_authorize_url_has_no_query_in_redirect_uri(monkeypatch):
    client = DouyinClient("awo", "secret")
    url = client.authorize_url(redirect_uri="https://ai.example.com/api/platform-accounts/douyin/callback", state="s1")
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    assert q["client_key"] == "awo" and q["response_type"] == "code" and q["scope"] == "user_info"
    assert q["redirect_uri"] == "https://ai.example.com/api/platform-accounts/douyin/callback"
    assert q["state"] == "s1"


# ── Service with a fake provider ───────────────────────────────────────────
class FakeProvider:
    key = "douyin"

    def __init__(self):
        self.exchanged: list[str] = []
        self.refreshed: list[str] = []
        self.renewed: list[str] = []
        self.profile_calls = 0
        self.fail_profile: Exception | None = None
        self.fail_refresh: Exception | None = None
        self.fail_renew: Exception | None = None

    def info(self):
        return ProviderInfo(key="douyin", display="抖音", capabilities=["login", "publish"], configured=True, max_grant_days=195)

    def build_authorize_url(self, state):
        return f"https://open.douyin.com/platform/oauth/connect/?state={state}"

    async def exchange_code(self, code):
        self.exchanged.append(code)
        return TokenGrant(
            external_id="open-1",
            access_token=f"act.{code}",
            refresh_token=f"rft.{code}",
            access_expires_at=NOW + timedelta(days=15),
            refresh_expires_at=NOW + timedelta(days=30),
            scopes="user_info",
        )

    async def refresh_access(self, refresh_token, *, refresh_expires_at=None):
        self.refreshed.append(refresh_token)
        if self.fail_refresh:
            raise self.fail_refresh
        return TokenGrant(
            external_id="open-1",
            access_token="act.refreshed",
            refresh_token=refresh_token,
            access_expires_at=NOW + timedelta(days=15),
            refresh_expires_at=refresh_expires_at or NOW + timedelta(days=30),
        )

    async def renew_refresh(self, refresh_token):
        self.renewed.append(refresh_token)
        if self.fail_renew:
            raise self.fail_renew
        return "rft.renewed", NOW + timedelta(days=30)

    async def fetch_profile(self, access_token, external_id):
        self.profile_calls += 1
        if self.fail_profile:
            raise self.fail_profile
        return Profile(external_id=external_id, nickname="李伟", avatar_url="https://x/a.jpg", union_id="u1")


@pytest.fixture
def fake_platform(monkeypatch):
    monkeypatch.setattr(get_config(), "wuying_channel_key", KEY)
    monkeypatch.setattr(get_config(), "secrets_master_key", "")
    set_cache(MemoryCache())
    original = get_provider("douyin")
    fake = FakeProvider()
    set_provider(fake)
    monkeypatch.setattr(service, "_now", lambda: NOW)
    yield fake
    set_provider(original)
    set_cache(None)


async def _bind(fake, workspace="ws-1", user="user-1"):
    started = await service.start_authorize(user_id=user, workspace_id=workspace, platform="douyin")
    state = started["state"]
    assert started["authorizeUrl"].endswith(state)
    return await service.complete_callback(platform="douyin", code="code-1", state=state, granted_scopes="user_info")


@pytest.mark.asyncio
async def test_bind_stores_encrypted_tokens_and_profile(fake_platform):
    row = await _bind(fake_platform)
    assert row.status == "bound" and row.external_id == "open-1" and row.nickname == "李伟"
    assert row.access_token_ciphertext.startswith("v1:") and "act.code-1" not in row.access_token_ciphertext
    assert decrypt_secret(row.access_token_ciphertext, "openbox:platform:douyin:access:v1", KEY) == "act.code-1"
    public = service.to_public(row)
    assert "access_token" not in json.dumps(public) and "ciphertext" not in json.dumps(public)
    assert public["scopes"] == ["user_info"] and public["renewalsLeft"] == 5
    # 30 days of refresh token + 5 renewals × 30 days = the "scan again by" date.
    assert public["estimatedExpiresAt"] == (NOW + timedelta(days=30 + 150)).isoformat()

    # The state is single-use.
    with pytest.raises(PlatformError) as exc:
        await service.complete_callback(platform="douyin", code="code-2", state="nope")
    assert exc.value.code == "PLATFORM_STATE_INVALID"


@pytest.mark.asyncio
async def test_rebinding_same_person_reuses_row_and_resets_renewals(fake_platform):
    first = await _bind(fake_platform)
    async with get_db_session() as db:
        row = (await db.execute(select(PlatformAccount).where(PlatformAccount.id == first.id))).scalar_one()
        row.renew_count = 4
        row.status = "expired"
        await db.commit()
    second = await _bind(fake_platform)
    assert second.id == first.id and second.status == "bound" and second.renew_count == 0
    rows = await service.list_accounts("ws-1")
    assert [r.id for r in rows] == [first.id]


@pytest.mark.asyncio
async def test_keep_alive_refreshes_access_and_renews_refresh_token(fake_platform):
    row = await _bind(fake_platform)
    async with get_db_session() as db:
        db_row = (await db.execute(select(PlatformAccount).where(PlatformAccount.id == row.id))).scalar_one()
        db_row.access_expires_at = NOW + timedelta(days=1)
        db_row.refresh_expires_at = NOW + timedelta(days=5)
        await db.commit()
    await service.refresh_due()
    assert fake_platform.refreshed == ["rft.code-1"]
    assert fake_platform.renewed == ["rft.code-1"]
    async with get_db_session() as db:
        db_row = (await db.execute(select(PlatformAccount).where(PlatformAccount.id == row.id))).scalar_one()
        assert db_row.renew_count == 1 and db_row.status == "bound"
        assert decrypt_secret(db_row.refresh_token_ciphertext, "openbox:platform:douyin:refresh:v1", KEY) == "rft.renewed"
        assert decrypt_secret(db_row.access_token_ciphertext, "openbox:platform:douyin:access:v1", KEY) == "act.refreshed"


@pytest.mark.asyncio
async def test_keep_alive_marks_expired_and_notifies_when_grant_is_gone(fake_platform):
    row = await _bind(fake_platform)
    fake_platform.fail_refresh = PlatformAuthRequired("10010: refresh_token 已过期")
    async with get_db_session() as db:
        db_row = (await db.execute(select(PlatformAccount).where(PlatformAccount.id == row.id))).scalar_one()
        db_row.access_expires_at = NOW - timedelta(hours=1)
        await db.commit()
    await service.refresh_due()
    async with get_db_session() as db:
        db_row = (await db.execute(select(PlatformAccount).where(PlatformAccount.id == row.id))).scalar_one()
        assert db_row.status == "expired" and "10010" in (db_row.last_error or "")
        notes = list((await db.execute(select(Notification).where(Notification.workspace_id == "ws-1"))).scalars())
        assert [n.kind for n in notes] == ["platform_auth_expired"]
    # A second tick does not spam a second notification and leaves the row alone.
    await service.refresh_due()
    async with get_db_session() as db:
        notes = list((await db.execute(select(Notification).where(Notification.workspace_id == "ws-1"))).scalars())
        assert len(notes) == 1


@pytest.mark.asyncio
async def test_keep_alive_tolerates_missing_renew_permission(fake_platform):
    row = await _bind(fake_platform)
    fake_platform.fail_renew = PlatformApiError(10004, "权限不足")
    async with get_db_session() as db:
        db_row = (await db.execute(select(PlatformAccount).where(PlatformAccount.id == row.id))).scalar_one()
        db_row.refresh_expires_at = NOW + timedelta(days=2)
        await db.commit()
    await service.refresh_due()
    async with get_db_session() as db:
        db_row = (await db.execute(select(PlatformAccount).where(PlatformAccount.id == row.id))).scalar_one()
        assert db_row.status == "bound" and db_row.renew_count == 0
        assert "renew_refresh_token" in (db_row.last_error or "")
        # Without the renewal permission the estimate collapses to the hard expiry.
        assert service.to_public(db_row)["estimatedExpiresAt"] == service.to_public(db_row)["refreshExpiresAt"]


@pytest.mark.asyncio
async def test_probe_refreshes_dead_access_token_then_reads_profile(fake_platform):
    row = await _bind(fake_platform)
    calls_before = fake_platform.profile_calls
    fake_platform.fail_profile = PlatformAuthRequired("28001008: access_token过期")
    probed = await service.probe(row.id, "ws-1")
    # First read fails, refresh happens, second read still fails → expired.
    assert fake_platform.refreshed == ["rft.code-1"]
    assert probed.status == "expired"
    assert fake_platform.profile_calls == calls_before + 2

    with pytest.raises(PlatformError):
        await service.probe(row.id, "ws-other")


@pytest.mark.asyncio
async def test_unbind_drops_tokens_and_hides_row(fake_platform):
    row = await _bind(fake_platform)
    gone = await service.unbind(row.id, "ws-1")
    assert gone.status == "revoked" and gone.access_token_ciphertext is None and gone.deleted_at is not None
    assert await service.list_accounts("ws-1") == []


# ── Publish + webhook ──────────────────────────────────────────────────────
class FakeOss:
    def __init__(self):
        self.copied: list[tuple[str, str]] = []

    async def copy(self, src, dest):
        self.copied.append((src, dest))
        return {"etag": "x"}

    def presign_get(self, key, expires_sec=3600, download_name=None, *, internal=False):
        assert not internal
        return f"https://bucket.oss-cn-shanghai.aliyuncs.com/{key}?Expires={expires_sec}"


class FakeClient:
    client_key = "awo"

    def __init__(self, short_link: str | None = None, short_link_error: Exception | None = None):
        self.short_link = short_link
        self.short_link_error = short_link_error
        self.get_share_bodies: list[dict] = []

    async def open_ticket(self):
        return "ticket-1"

    async def share_id(self, *, need_callback=True, default_hashtag=""):
        return "share-1"

    async def get_share_schema(self, body):
        self.get_share_bodies.append(body)
        if self.short_link_error:
            raise self.short_link_error
        return self.short_link or "snssdk1128://webview?url=short"


@pytest.mark.asyncio
async def test_publish_stages_non_ascii_key_and_webhook_completes_job(fake_platform, monkeypatch):
    fake_platform.client = FakeClient(short_link_error=PlatformApiError(28001018, "应用未获得该能力"))
    async with get_db_session() as db:
        db.add(
            FileAsset(
                id="asset-1",
                user_id="user-1",
                workspace_id="ws-1",
                name="成片.mp4",
                oss_key="assets/user-1/asset-1/成片.mp4",
                mime="video/mp4",
                size=10 * 1024 * 1024,
                status="ready",
                created_at=NOW,
            )
        )
        db.add(
            FileAsset(
                id="asset-big",
                user_id="user-1",
                workspace_id="ws-1",
                name="big.mp4",
                oss_key="assets/user-1/asset-big/big.mp4",
                mime="video/mp4",
                size=200 * 1024 * 1024,
                status="ready",
                created_at=NOW,
            )
        )
        await db.commit()
    oss = FakeOss()
    job, schema = await service.create_publish_job(
        oss=oss, user_id="user-1", workspace_id="ws-1", file_asset_id="asset-1", title="标题", hashtags=["装修"]
    )
    assert oss.copied == [("assets/user-1/asset-1/成片.mp4", f"publish/{job.id}/video.mp4")]
    assert job.status == "pending" and job.share_id == "share-1"
    # get_share was tried with the structured body, then the local schema took over.
    body = fake_platform.client.get_share_bodies[0]
    assert body["title"] == "标题" and body["hashtag_list"] == ["装修"] and body["state"] == "share-1"
    assert body["share_to_publish"] == 1 and body["client_ticket"] == "ticket-1"
    assert body["expire_at"] == int((NOW + timedelta(hours=1)).timestamp())
    assert job.error == "schema_source=local"
    q = {k: v[0] for k, v in parse_qs(urlparse(schema).query).items()}
    assert q["state"] == "share-1" and q["video_path"].endswith(f"publish/{job.id}/video.mp4?Expires=7200")

    with pytest.raises(PlatformError) as exc:
        await service.create_publish_job(oss=oss, user_id="user-1", workspace_id="ws-1", file_asset_id="asset-big")
    assert exc.value.code == "PUBLISH_FILE_TOO_LARGE"
    with pytest.raises(PlatformError) as exc:
        await service.create_publish_job(oss=oss, user_id="user-1", workspace_id="ws-2", file_asset_id="asset-1")
    assert exc.value.code == "PUBLISH_FILE_NOT_FOUND"

    account = await _bind(fake_platform)
    changed = await service.handle_douyin_event(
        {
            "event": "create_video",
            "from_user_id": "open-1",
            "client_key": "awo",
            "content": {"share_id": "share-1", "item_id": "item-9", "video_id": "vid-9", "has_default_hashtag": True},
        }
    )
    assert changed is True
    done = await service.get_job(job.id, "ws-1")
    assert done.status == "published" and done.item_id == "item-9" and done.platform_account_id == account.id
    assert await service.handle_douyin_event({"event": "create_video", "content": {"share_id": "unknown"}}) is False


@pytest.mark.asyncio
async def test_publish_prefers_platform_short_link(fake_platform):
    fake_platform.client = FakeClient(short_link="snssdk1128://webview?url=https%3A%2F%2Fopen.douyin.com%2Fslink")
    async with get_db_session() as db:
        db.add(
            FileAsset(
                id="asset-2", user_id="user-1", workspace_id="ws-1", name="clip.mp4",
                oss_key="assets/user-1/asset-2/clip.mp4", mime="video/mp4", size=1024,
                status="ready", created_at=NOW,
            )
        )
        await db.commit()
    job, schema = await service.create_publish_job(
        oss=FakeOss(), user_id="user-1", workspace_id="ws-1", file_asset_id="asset-2", title="t"
    )
    assert schema.startswith("snssdk1128://webview?url=") and job.error is None


@pytest.mark.asyncio
async def test_pending_job_expires_when_read_after_ttl(fake_platform):
    async with get_db_session() as db:
        db.add(
            PublishJob(
                id="pub-old",
                workspace_id="ws-1",
                user_id="user-1",
                platform="douyin",
                file_asset_id="asset-1",
                hashtags=[],
                status="pending",
                expires_at=NOW - timedelta(minutes=1),
                created_at=NOW - timedelta(hours=2),
                updated_at=NOW - timedelta(hours=2),
            )
        )
        await db.commit()
    assert (await service.get_job("pub-old", "ws-1")).status == "expired"


@pytest.mark.asyncio
async def test_webhook_verifies_signature_and_echoes_challenge(monkeypatch):
    from api import webhooks_douyin

    monkeypatch.setattr(get_config(), "douyin_client_key", "awo")
    monkeypatch.setattr(get_config(), "douyin_client_secret", "sec")
    set_cache(MemoryCache())
    seen: list[dict] = []

    async def fake_handle(payload):
        seen.append(payload)
        return True

    monkeypatch.setattr(webhooks_douyin.service, "handle_douyin_event", fake_handle)
    app = FastAPI()
    app.include_router(webhooks_douyin.router)
    client = DouyinClient("awo", "sec")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        body = json.dumps({"event": "verify_webhook", "client_key": "awo", "content": {"challenge": 12345}}).encode()
        resp = await http.post("/api/webhooks/douyin", content=body, headers={"content-type": "application/json"})
        assert resp.status_code == 200 and resp.json() == {"challenge": 12345}

        event = json.dumps({"event": "create_video", "content": {"share_id": "s"}}).encode()
        bad = await http.post("/api/webhooks/douyin", content=event, headers={"X-Douyin-Signature": "deadbeef"})
        assert bad.status_code == 401 and seen == []

        good_sig = client.webhook_signature(event)
        ok = await http.post(
            "/api/webhooks/douyin", content=event, headers={"X-Douyin-Signature": good_sig, "Msg-Id": "m1"}
        )
        assert ok.status_code == 200 and ok.json()["handled"] is True and len(seen) == 1
        dup = await http.post(
            "/api/webhooks/douyin", content=event, headers={"X-Douyin-Signature": good_sig, "Msg-Id": "m1"}
        )
        assert dup.json().get("duplicate") is True and len(seen) == 1
    set_cache(None)
