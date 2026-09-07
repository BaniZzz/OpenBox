"""Errors shared by every platform provider."""


class PlatformError(Exception):
    """Base: something the caller can show as a stable code."""

    code = "PLATFORM_ERROR"

    def __init__(self, message: str = "", *, code: str | None = None, detail: dict | None = None):
        super().__init__(message or self.code)
        if code:
            self.code = code
        self.detail = detail or {}


class PlatformNotConfigured(PlatformError):
    code = "PLATFORM_NOT_CONFIGURED"


class PlatformAuthRequired(PlatformError):
    """The stored grant is gone: the person has to scan again."""

    code = "PLATFORM_AUTH_REQUIRED"


class PlatformApiError(PlatformError):
    """The platform answered with an error code; `platform_code` is theirs."""

    code = "PLATFORM_API_ERROR"

    def __init__(self, platform_code: int | str, description: str = "", *, retryable: bool = False):
        super().__init__(f"{platform_code}: {description}".strip(": "))
        self.platform_code = platform_code
        self.description = description
        self.retryable = retryable
