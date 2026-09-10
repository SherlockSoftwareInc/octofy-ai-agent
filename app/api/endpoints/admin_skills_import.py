import threading

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from pathlib import Path

from app.core.auth import get_current_active_admin
from app.models.user_models import User
from app.services.source_resolver import resolve_known_source_id, resolve_or_primary
from app.services.skills_importer import (
    get_rebuild_status,
    import_and_rebuild,
    run_rebuild,
    start_rebuild,
)

router = APIRouter()

SKILLS_ROOT = Path(__file__).resolve().parents[3] / "skills"


class ImportRequest(BaseModel):
    folder_path: str
    source_id: str


@router.post("/skills/import")
def import_skills(body: ImportRequest, current_user: User = Depends(get_current_active_admin)):
    source_id = resolve_or_primary(body.source_id)
    report = import_and_rebuild(body.folder_path, str(SKILLS_ROOT), source_id)
    if report.rejected_files:
        raise HTTPException(status_code=400, detail={"rejected_files": report.rejected_files, "errors": report.errors})
    return report.__dict__


@router.post("/skills/rebuild/{source_id}")
def rebuild(
    source_id: str,
    folder_path: str = None,
    current_user: User = Depends(get_current_active_admin),
):
    source_id = resolve_known_source_id(source_id)
    try:
        status = start_rebuild(source_id, folder_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    threading.Thread(
        target=run_rebuild,
        args=(source_id, status.get("folder")),
        daemon=True,
        name=f"reload-{source_id[:8]}",
    ).start()
    return status


@router.get("/skills/rebuild-status/{source_id}")
def rebuild_status(source_id: str, current_user: User = Depends(get_current_active_admin)):
    return get_rebuild_status(source_id)
