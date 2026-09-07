"""Provider contract for the authorization centre."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class TokenGrant:
    """What an authorization (or a refresh) hands back, normalised."""

    external_id: str
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    scopes: str = ""
    union_id: str | None = None


@dataclass
class Profile:
    external_id: str
    nickname: str | None = None
    avatar_url: str | None = None
    union_id: str | None = None


@dataclass
class ProviderInfo:
    key: str
    display: str
    capabilities: list[str] = field(default_factory=list)
    configured: bool = False
    #: Longest stretch without a new scan, in days, for the page to explain.
    max_grant_days: int | None = None


class PlatformProvider(Protocol):
    key: str

    def info(self) -> ProviderInfo: ...

    def build_authorize_url(self, state: str, *, call_app: bool = False) -> str: ...

    async def exchange_code(self, code: str) -> TokenGrant: ...

    async def refresh_access(self, refresh_token: str) -> TokenGrant: ...

    async def renew_refresh(self, refresh_token: str) -> tuple[str, datetime]: ...

    async def fetch_profile(self, access_token: str, external_id: str) -> Profile: ...
