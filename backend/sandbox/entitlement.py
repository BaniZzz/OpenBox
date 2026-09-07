"""Authoritative sandbox access, independent of credit-meter shadow/off mode."""
from billing.service import now
from billing.subscriptions import active_subscription
from core.config import get_config
from db.base import get_db_session


class SandboxSubscriptionRequired(PermissionError):
    code = "SANDBOX_SUBSCRIPTION_REQUIRED"
    detail = "普通 LLM 对话可继续使用；执行 sandbox 或连接无影云需要有效的付费套餐。"

    def __init__(self):
        super().__init__(self.detail)
        self.payload = {"state": "subscription_required", "code": self.code, "detail": self.detail}


def subscription_sandbox_enabled() -> bool:
    config = get_config()
    return config.sandbox_provider == "wuying" and config.wuying_routing == "per_desktop"


async def require_sandbox_subscription(workspace_id: str):
    """No cache: a retained client/URL must not outlive the paid subscription."""
    async with get_db_session() as db:
        sub = await active_subscription(db, workspace_id, now()) if workspace_id else None
        if sub is None or sub.plan_id == "free":
            raise SandboxSubscriptionRequired()
        return sub


async def watch_sandbox_subscription(workspace_id: str, interval: float = 5):
    """A WebSocket watchdog; callers cancel both pumps when this raises."""
    import asyncio
    while True:
        await require_sandbox_subscription(workspace_id)
        await asyncio.sleep(interval)
