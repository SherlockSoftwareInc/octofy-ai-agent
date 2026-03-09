import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.endpoints import data_sources
from app.core.auth import get_current_user


class _DummyDb:
    pass


def _run_async(coro):
    return asyncio.run(coro)


def test_route_uses_get_current_user_dependency():
    route = next(
        r
        for r in data_sources.router.routes
        if r.path == "/data-sources" and "GET" in r.methods
    )
    dependencies = [dep.call for dep in route.dependant.dependencies]

    assert get_current_user in dependencies


def test_get_current_user_requires_api_key():
    with pytest.raises(HTTPException) as exc:
        _run_async(get_current_user(x_api_key=None, db=_DummyDb()))

    assert exc.value.status_code == 401
    assert "Missing API key" in exc.value.detail


def test_get_current_user_rejects_invalid_api_key(monkeypatch):
    import app.services.user_service as user_service

    monkeypatch.setattr(user_service, "get_user_by_api_key", lambda db, key: None)

    with pytest.raises(HTTPException) as exc:
        _run_async(get_current_user(x_api_key="invalid-key", db=_DummyDb()))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid API key"


def test_list_data_sources_allows_valid_user_key_and_returns_id_name(monkeypatch):
    import app.services.user_service as user_service

    valid_user = SimpleNamespace(is_active=True, role="user")
    monkeypatch.setattr(
        user_service,
        "get_user_by_api_key",
        lambda db, key: valid_user if key == "valid-user-key" else None,
    )

    monkeypatch.setattr(
        data_sources.SkillsService,
        "load_data_sources_index",
        lambda self: [
            SimpleNamespace(
                source_id="ds-1",
                name="Northwind",
                description="Northwind source",
                keywords=["sales"],
                status="Active",
            )
        ],
    )
    monkeypatch.setattr(data_sources, "_get_object_count_by_name", lambda _: 3)

    current_user = _run_async(get_current_user(x_api_key="valid-user-key", db=_DummyDb()))
    response = data_sources.list_data_sources(current_user=current_user)

    assert response.data_sources[0].source_id == "ds-1"
    assert response.data_sources[0].friendly_name == "Northwind"
    assert response.total_objects == 3
