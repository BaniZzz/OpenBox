"""Registration, project ordering, and the legacy starter-name repair."""
import importlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from api import projects as project_api
from db.base import get_db_session
from db.models.project import Project
from db.repository.user_repo import PgUserRepo
from project import workspace


async def test_registered_starter_name_and_project_creation_order():
    suffix = uuid4().hex
    user = await PgUserRepo().create(
        id=suffix, username=suffix, password_hash="unused",
    )
    workspace_id = user["default_workspace_id"]
    starter = await workspace.ensure_default_project(user["id"], workspace_id)
    assert starter.name == "默认空间"
    assert starter.directory == "/workspace/default"
    older = await workspace.create_project(user["id"], workspace_id, "First project")
    newer = await workspace.create_project(user["id"], workspace_id, "Second project")
    assert [p["id"] for p in await project_api.list_projects({
        "user_id": user["id"], "workspace_id": workspace_id,
    })] == [newer.id, older.id, starter.id]

    # Renaming must not promote an older project. Equal creation timestamps
    # (imports or concurrent creation) still produce a stable order.
    await workspace.rename_project(older.id, user["id"], workspace_id, "Renamed")
    tied = datetime.now(timezone.utc) + timedelta(days=1)
    hidden = await workspace.create_project(user["id"], workspace_id, "Hidden project")
    async with get_db_session() as db:
        for project_id in (older.id, newer.id):
            (await db.get(Project, project_id)).created_at = tied
        await db.execute(sa.update(Project).where(Project.id == hidden.id).values(is_deleted=True))
    assert [p.id for p in await workspace.list_projects(workspace_id)] == [
        *sorted([newer.id, older.id], reverse=True), starter.id,
    ]
    another = await PgUserRepo().create(
        id=uuid4().hex, username=uuid4().hex, password_hash="unused",
    )
    assert len(await workspace.list_projects(another["default_workspace_id"])) == 1


def test_legacy_name_repair_keeps_custom_names_paths_and_timestamps(monkeypatch):
    migration = importlib.import_module(
        "db.migrations.versions.f3a5b7c9d1e4_repair_registered_default_project_names"
    )
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT, slug TEXT, updated_at TEXT)"
        ))
        original = [
            ("legacy", "Default", "default", "2026-09-06"),
            ("renamed", "我的工作", "default", "2026-09-06"),
            ("custom", "Default", "my-project", "2026-09-06"),
            ("current", "默认空间", "default", "2026-09-06"),
        ]
        for row in original:
            connection.execute(sa.text("INSERT INTO projects VALUES (:id,:name,:slug,:updated_at)"),
                               dict(zip(("id", "name", "slug", "updated_at"), row)))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        migration.upgrade()
        migration.downgrade()
        rows = {r[0]: tuple(r) for r in connection.execute(sa.text("SELECT * FROM projects"))}
        assert rows["legacy"] == ("legacy", "默认空间", "default", "2026-09-06")
        assert all(rows[r[0]] == r for r in original[1:])
    engine.dispose()
