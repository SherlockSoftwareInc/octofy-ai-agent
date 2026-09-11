from fastapi import HTTPException

from app.services.source_resolver import require_source_id


def test_require_source_id_missing():
    try:
        require_source_id(None)
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "source_id is required"


def test_require_source_id_blank():
    try:
        require_source_id("   ")
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert exc.detail == "source_id is required"
