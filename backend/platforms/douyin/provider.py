"""Douyin as an authorization-centre provider."""
from datetime import datetime, timedelta, timezone

from core.config import get_config
from platforms.base import Profile, ProviderInfo, TokenGrant
from platforms.douyin.client import DouyinClient
from platforms.errors import PlatformNotConfigured

KEY = "douyin"
DISPLAY = "抖音"
#: Only what the page needs. Publishing uses application credentials, not a
#: user scope, so this is the whole request (Douyin caps a request at 3).
LOGIN_SCOPE = "user_info"
#: 15 (access) + 30 (refresh) + 5 × 30 (renewals), per the docs.
MAX_GRANT_DAYS = 195
CALLBACK_PATH = "/api/platform-accounts/douyin/callback"


def redirect_uri() -> str:
    config = get_config()
    if config.douyin_redirect_uri:
        return config.douyin_redirect_uri
    base = (config.public_base_url or "").rstrip("/")
    return f"{base}{CALLBACK_PATH}" if base else ""


def _expires(seconds: int | str | None, default: int) -> datetime:
    try:
        n = int(seconds or default)
    except (TypeError, ValueError):
        n = default
    return datetime.now(timezone.utc) + timedelta(seconds=n)


def _grant(data: dict, *, fallback_refresh: str | None = None, fallback_refresh_expiry: datetime | None = None) -> TokenGrant:
    refresh_token = str(data.get("refresh_token") or fallback_refresh or "")
    refresh_expires = (
        _expires(data["refresh_expires_in"], 30 * 86400)
        if data.get("refresh_expires_in")
        else (fallback_refresh_expiry or _expires(None, 30 * 86400))
    )
    return TokenGrant(
        external_id=str(data.get("open_id") or ""),
        access_token=str(data.get("access_token") or ""),
        refresh_token=refresh_token,
        access_expires_at=_expires(data.get("expires_in"), 15 * 86400),
        refresh_expires_at=refresh_expires,
        scopes=str(data.get("scope") or ""),
    )


class DouyinProvider:
    key = KEY

    def __init__(self, client: DouyinClient | None = None):
        self._client = client

    @property
    def client(self) -> DouyinClient:
        if self._client is None:
            config = get_config()
            self._client = DouyinClient(config.douyin_client_key, config.douyin_client_secret)
        return self._client

    def configured(self) -> bool:
        config = get_config()
        return bool(config.douyin_client_key and config.douyin_client_secret and redirect_uri())

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            key=KEY,
            display=DISPLAY,
            capabilities=["login", "publish"],
            configured=self.configured(),
            max_grant_days=MAX_GRANT_DAYS,
        )

    def build_authorize_url(self, state: str) -> str:
        uri = redirect_uri()
        if not uri:
            raise PlatformNotConfigured("DOUYIN_REDIRECT_URI or PUBLIC_BASE_URL must be set")
        return self.client.authorize_url(redirect_uri=uri, state=state, scope=LOGIN_SCOPE)

    async def exchange_code(self, code: str) -> TokenGrant:
        return _grant(await self.client.exchange_code(code))

    async def refresh_access(self, refresh_token: str, *, refresh_expires_at: datetime | None = None) -> TokenGrant:
        data = await self.client.refresh_access_token(refresh_token)
        # Refreshing the access token does not move the refresh token's expiry;
        # the response echoes a value but the docs say it is unchanged.
        return _grant(
            {k: v for k, v in data.items() if k != "refresh_expires_in"},
            fallback_refresh=refresh_token,
            fallback_refresh_expiry=refresh_expires_at,
        )

    async def renew_refresh(self, refresh_token: str) -> tuple[str, datetime]:
        data = await self.client.renew_refresh_token(refresh_token)
        return str(data.get("refresh_token") or ""), _expires(data.get("expires_in"), 30 * 86400)

    async def fetch_profile(self, access_token: str, external_id: str) -> Profile:
        data = await self.client.userinfo(access_token, external_id)
        return Profile(
            external_id=str(data.get("open_id") or external_id),
            nickname=data.get("nickname") or None,
            avatar_url=data.get("avatar") or None,
            union_id=data.get("union_id") or None,
        )
