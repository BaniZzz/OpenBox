"""The environment badge endpoint is public and reflects APP_ENV."""
import httpx

from core.config import get_config
from main import create_app


async def _get(app, path):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path)


async def test_environment_is_public_and_reports_configured_name(monkeypatch):
    monkeypatch.setattr(get_config(), "app_env", "staging")
    response = await _get(create_app(), "/api/environment")
    assert response.status_code == 200
    assert response.json() == {"name": "staging"}


async def test_environment_defaults_to_empty(monkeypatch):
    monkeypatch.setattr(get_config(), "app_env", "")
    response = await _get(create_app(), "/api/environment")
    assert response.json() == {"name": ""}
