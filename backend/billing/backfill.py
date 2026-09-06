"""Opt-in historical estimates; never debit a balance or rewrite paid usage.

Run locally: python -m billing.backfill. Existing message tokens predate reliable
cache-write attribution, so their old `cache` bucket is estimated as cache reads.
"""
import asyncio

from sqlalchemy import exists, select

from billing.pricing import catalogue, normalize_usage, quote
from billing.service import lock_balance
from core.identifier import ascending as generate_id
from db.base import get_db_session
from db.models.billing import UsageEvent
from db.models.message import Message
from db.models.session import Session


async def backfill_history() -> dict:
    rates = catalogue()
    result = {"inserted": 0, "unpriced": 0, "invalid_usage": 0}
    cursor = ""
    while True:
        async with get_db_session() as db:
            rows = (await db.execute(select(Message, Session.workspace_id, Session.title)
                .join(Session, Session.id == Message.session_id)
                .where(Message.role == "assistant", Message.id > cursor, Message.tokens.is_not(None),
                    ~exists().where(UsageEvent.message_id == Message.id))
                .order_by(Message.id).limit(200))).all()
        if not rows:
            return result
        for message, workspace_id, title in rows:
            cursor = message.id
            try:
                tokens = normalize_usage(message.tokens)
            except ValueError:
                result["invalid_usage"] += 1
                continue
            if not tokens["total"]:
                continue
            # A transport prefix is not the model vendor; keep the exact route.
            model_id = message.model or message.model_id or "unknown"
            price = quote(model_id, tokens, at=message.created_at, rates=rates)
            async with get_db_session() as db:
                await lock_balance(db, workspace_id)
                if await db.scalar(select(UsageEvent.id).where(UsageEvent.message_id == message.id).limit(1)):
                    continue
                db.add(UsageEvent(id=generate_id("usage"), idempotency_key=f"history:{message.id}",
                    workspace_id=workspace_id, user_id=message.user_id, session_id=message.session_id,
                    message_id=message.id, session_title=title or message.session_id, model_id=model_id,
                    kind="compaction" if message.summary else "chat", tokens=tokens,
                    total_tokens=tokens["total"], credits=price.credits,
                    status="historical" if price.credits is not None else "unpriced",
                    pricing={**price.snapshot, "historical_estimate": True,
                        "note": "Current tariff estimate; legacy cache treated as reads; no retrospective debit"},
                    created_at=message.created_at))
                result["inserted"] += 1
                result["unpriced"] += price.credits is None


async def price_unpriced_history() -> int:
    """Fill a previously unknown historical estimate; settled events are immutable."""
    rates = catalogue()
    changed = 0
    async with get_db_session() as db:
        ids = (await db.scalars(select(UsageEvent.id).where(UsageEvent.status == "unpriced"))).all()
    for event_id in ids:
        async with get_db_session() as db:
            event = await db.get(UsageEvent, event_id)
            if not event.pricing.get("historical_estimate"):
                continue
            await lock_balance(db, event.workspace_id)
            await db.refresh(event)
            if event.status != "unpriced":
                continue
            price = quote(event.model_id, event.tokens, at=event.created_at, rates=rates)
            if price.credits is None:
                continue
            event.credits = price.credits
            event.pricing = {**price.snapshot, "historical_estimate": True,
                "note": "Current tariff estimate; legacy cache treated as reads; no retrospective debit"}
            event.status = "historical"
            changed += 1
    return changed


async def main():
    import argparse
    from dotenv import load_dotenv
    from core.config import load_config
    from db.base import init_engine, close_engine
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--price-unpriced-history", action="store_true")
    args = parser.parse_args()
    config = load_config()
    init_engine(config.database_url)
    try:
        print(await backfill_history())
        if args.price_unpriced_history:
            print({"historical_prices_added": await price_unpriced_history()})
    finally:
        await close_engine()


if __name__ == "__main__":
    asyncio.run(main())
