"""会话级 token 累计：每步开头刷新上下文进度条不能把上一步累加的总量覆盖掉。

2026-09-02 上海 gw2 实测：10 步会话每条消息的 tokens 都对，但 sessions.token_usage
只等于最后一步。原因是 loop 每步开始把运行开始时加载的旧 token_usage 快照
（只改了 context/limit）整个写回，冲掉了 update_session_tokens 上一步累加的结果。
"""
import uuid
from datetime import datetime, timezone

from models.message import TokenUsage
from session.session import (
    get_session,
    update_session_context,
    update_session_tokens,
)

USER = "tok-acc-user"


async def _insert_session(session_id: str, model: str = "anthropic/claude-sonnet-4"):
    from db.base import get_db_session
    from db.models.session import Session as SessionORM

    now = datetime.now(timezone.utc)
    async with get_db_session() as db:
        db.add(SessionORM(
            id=session_id,
            user_id=USER,
            project_id="default",
            title="t",
            model=model,
            status="idle",
            token_usage={},
            created_at=now,
            updated_at=now,
        ))


async def _run_step(session_id: str, step: TokenUsage, ctx: int, limit: int):
    """模拟 loop 一步：开头刷新进度条（context/limit），结尾累加本步 tokens。"""
    await update_session_context(session_id, context=ctx, limit=limit, user_id=USER)
    await update_session_tokens(session_id, step, user_id=USER)


async def test_two_steps_accumulate_input_and_output():
    sid = "sess_" + uuid.uuid4().hex[:10]
    await _insert_session(sid)

    step1 = TokenUsage(input=10509, output=80, cache=100, total=10589, cost=0.01)
    step2 = TokenUsage(input=13249, output=119, cache=200, total=13368, cost=0.02)

    await _run_step(sid, step1, ctx=10000, limit=200_000)
    await _run_step(sid, step2, ctx=13000, limit=200_000)

    final = await get_session(sid, user_id=USER)
    assert final is not None and final.token_usage is not None
    tu = final.token_usage
    assert tu.input == step1.input + step2.input
    assert tu.output == step1.output + step2.output
    assert tu.cache == step1.cache + step2.cache
    assert tu.total == step1.total + step2.total
    assert abs(tu.cost - (step1.cost + step2.cost)) < 1e-9
    # context 是最后一步的窗口大小，不累加
    assert tu.context == step2.total
    assert tu.limit > 0


async def test_update_session_context_only_touches_context_and_limit():
    sid = "sess_" + uuid.uuid4().hex[:10]
    await _insert_session(sid)

    await update_session_tokens(sid, TokenUsage(input=500, output=50, total=550, cost=0.005), user_id=USER)
    before = (await get_session(sid, user_id=USER)).token_usage
    assert before is not None and before.input == 500

    returned = await update_session_context(sid, context=4321, limit=128_000, user_id=USER)
    assert returned is not None
    after = (await get_session(sid, user_id=USER)).token_usage

    assert after.context == 4321
    assert after.limit == 128_000
    assert after.input == before.input
    assert after.output == before.output
    assert after.cache == before.cache
    assert after.total == before.total
    assert after.cost == before.cost


async def test_update_session_context_missing_session_returns_none():
    assert await update_session_context("sess_does_not_exist", context=1, limit=2, user_id=USER) is None
