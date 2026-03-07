"""
Live integration test for the backend data source resolve service.

This test uses the user-provided parameters:
- Endpoint: http://localhost:8000/
- API key: 2pXZdP9tmnlGAiAC-7rRgIiFSV4QPIBFIm4yDT0D72IoCDpmwruLy8Jp80HaNTKc
- Server name: SSI01
- Database name: NORTHWIND
"""

from __future__ import annotations

import os
import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
API_KEY = "2pXZdP9tmnlGAiAC-7rRgIiFSV4QPIBFIm4yDT0D72IoCDpmwruLy8Jp80HaNTKc"
SERVER_NAME = "SSI01"
DATABASE_NAME = "NORTHWIND"


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
    test_resolve_service_with_northwind_params()
    print("[PASS] Resolve service test succeeded for SSI01/NORTHWIND")
