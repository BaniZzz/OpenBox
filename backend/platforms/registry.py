"""Providers by key. Adding a platform = one entry here + one package."""
from platforms.douyin.provider import DouyinProvider
from platforms.errors import PlatformError

_providers = {DouyinProvider.key: DouyinProvider()}


def get_provider(key: str):
    provider = _providers.get(key)
    if provider is None:
        raise PlatformError(f"unknown platform: {key}", code="PLATFORM_UNKNOWN")
    return provider


def list_providers() -> list:
    return list(_providers.values())


def set_provider(provider) -> None:
    """Tests swap in a provider with a fake client."""
    _providers[provider.key] = provider
