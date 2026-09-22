"""
Live integration test for the backend data source resolve service.

This test needs a running backend plus valid credentials, so both come from the
environment (never hardcode them — this file is committed):

- ``BASE_URL``      backend root, default ``http://localhost:8000``
- ``API_KEY``       ``X-API-Key`` of an active user (required; the test skips without it)
- ``SERVER_NAME``   default ``SSI01``
- ``DATABASE_NAME`` default ``NORTHWIND``

Run with::

    API_KEY=<your-user-api-key> python -m pytest tests/test_resolve_service_live.py
"""

from __future__ import annotations

import os

import pytest
import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY")
SERVER_NAME = os.getenv("SERVER_NAME", "SSI01")
DATABASE_NAME = os.getenv("DATABASE_NAME", "NORTHWIND")

pytestmark = pytest.mark.skipif(
    not API_KEY,
    reason="API_KEY is not set; skipping the live resolve-service test",
)


def test_resolve_service_with_northwind_params() -> None:
    """Verify resolve endpoint can resolve source_id for SSI01/NORTHWIND."""
    headers = {"X-API-Key": API_KEY}
    params = {"server": SERVER_NAME, "database": DATABASE_NAME}

    # Actual route is mounted under /api/v1/admin in app/main.py
    url = f"{BASE_URL}/api/v1/admin/data-sources/resolve"
    response = requests.get(url, headers=headers, params=params, timeout=30)

    assert response.status_code == 200, (
        f"Expected 200 from {url}, got {response.status_code}: {response.text}"
    )

    data = response.json()
    assert data.get("source_id"), "source_id should be present"
    assert data.get("name"), "name should be present"
    assert data.get("status") == "active", f"Expected active status, got: {data.get('status')}"

    # With the requested behavior, database should be the primary matching key.
    resolved_database = (data.get("database") or "").upper()
    assert resolved_database == DATABASE_NAME, (
        f"Expected database {DATABASE_NAME}, got {data.get('database')}"
    )


if __name__ == "__main__":
    if not API_KEY:
        raise SystemExit("API_KEY is not set; refusing to run the live test without credentials")
    test_resolve_service_with_northwind_params()
    print(f"[PASS] Resolve service test succeeded for {SERVER_NAME}/{DATABASE_NAME}")
