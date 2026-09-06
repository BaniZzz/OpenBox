"""Fleet administration remains admin-only and exposes alert lifecycle."""
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from auth.middleware import get_current_user
from db.base import get_db_session
from db.models.fleet import FleetAlert, FleetSnapshot
from db.repository.user_repo import PgUserRepo
from main import create_app


async def _request(app, identity, method, path, body=None):
    async def current_user():
        return dict(identity)

    app.dependency_overrides[get_current_user] = current_user
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, json=body)
    finally:
        app.dependency_overrides.clear()


async def test_admin_reads_snapshot_and_acks_and_mutes_alert():
    suffix = uuid.uuid4().hex[:10]
    user = await PgUserRepo().create(
        id=f"fleet-admin-{suffix}", username=f"fleet-admin-{suffix}",
        password_hash="unused", role="admin",
    )
    now = datetime.now(timezone.utc)
    alert_id = f"flt-{suffix}"
    async with get_db_session() as session:
        session.add(FleetSnapshot(
            id=f"fsp-{suffix}", taken_at=now, source="ecd", ok=True,
            payload={"desktops": []}, error=None,
        ))
        session.add(FleetAlert(
            id=alert_id, rule="ghost", severity="critical",
            resource_type="desktop", resource_id=f"ecd-{suffix}", message="ghost",
            detail={}, first_seen_at=now, last_seen_at=now,
        ))
    app = create_app()
    identity = {"user_id": user["id"], "role": "admin"}

    snapshot = await _request(app, identity, "GET", "/api/admin/fleet/snapshots/latest")
    alerts = await _request(app, identity, "GET", "/api/admin/fleet/alerts")
    ack = await _request(app, identity, "POST", f"/api/admin/fleet/alerts/{alert_id}/ack")
    mute = await _request(
        app, identity, "POST", f"/api/admin/fleet/alerts/{alert_id}/mute",
        {"until": (now + timedelta(hours=1)).isoformat()},
    )

    assert snapshot.status_code == 200
    assert any(row["source"] == "ecd" for row in snapshot.json()["sources"])
    assert alerts.status_code == 200
    assert any(row["id"] == alert_id for row in alerts.json()["items"])
    assert ack.status_code == 200
    assert mute.status_code == 200


async def test_non_admin_cannot_read_fleet():
    suffix = uuid.uuid4().hex[:10]
    user = await PgUserRepo().create(
        id=f"fleet-user-{suffix}", username=f"fleet-user-{suffix}",
        password_hash="unused",
    )
    response = await _request(
        create_app(), {"user_id": user["id"], "role": "user"},
        "GET", "/api/admin/fleet/pool",
    )
    assert response.status_code == 403


async def test_admin_can_preview_pool_ensure(monkeypatch):
    suffix = uuid.uuid4().hex[:10]
    user = await PgUserRepo().create(
        id=f"fleet-ensure-{suffix}", username=f"fleet-ensure-{suffix}",
        password_hash="unused", role="admin",
    )
    from sandbox.pool import pool_service

    async def ensure_prewarm(*, dry_run, actor):
        assert dry_run is True
        assert actor == user["id"]
        return {
            "status": "dry_run", "current": 4, "target": 5,
            "gap": 1, "quantity": 1, "unit_price": 200, "currency": "CNY",
        }

    monkeypatch.setattr(pool_service, "ensure_prewarm", ensure_prewarm)
    response = await _request(
        create_app(), {"user_id": user["id"], "role": "admin"},
        "POST", "/api/admin/fleet/pool/ensure?dry_run=true",
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 1


async def test_admin_renew_forwards_explicit_approval(monkeypatch):
    suffix = uuid.uuid4().hex[:10]
    user = await PgUserRepo().create(
        id=f"fleet-renew-{suffix}", username=f"fleet-renew-{suffix}",
        password_hash="unused", role="admin",
    )
    from sandbox.pool import pool_service

    async def renew(desktop_id, actor, *, approve):
        assert desktop_id == "ecd-renew"
        assert actor == user["id"]
        assert approve is True
        return {"desktop_id": desktop_id, "pool_state": "prewarm"}

    monkeypatch.setattr(pool_service, "renew", renew)
    response = await _request(
        create_app(), {"user_id": user["id"], "role": "admin"},
        "POST", "/api/admin/fleet/desktops/ecd-renew/renew", {"approve": True},
    )
    assert response.status_code == 200
    assert response.json()["desktop_id"] == "ecd-renew"
