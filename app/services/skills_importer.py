"""Copy-in skills folder and rebuild vectors for a source_id."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from app.services.stores.schema_contracts import COLLECTIONS
from app.services.stores.skills_folder import (
    ImportReport,
    import_skills_folder,
    rebuild_vectors_from_folder,
    resolve_data_source_folder,
)

_rebuild_status: Dict[str, Dict[str, Any]] = {}


def _status(source_id: str, **fields) -> Dict[str, Any]:
    current = _rebuild_status.get(source_id) or {"source_id": source_id, "status": "idle", "message": ""}
    current.update(fields)
    current["source_id"] = source_id
    _rebuild_status[source_id] = current
    return current


def _require_milvus():
    from app.services.stores.milvus_provider import MilvusProvider

    milvus = MilvusProvider()
    if not getattr(milvus, "_connected", False):
        raise RuntimeError("Milvus is not connected")
    return milvus


def _clear_provider_caches() -> None:
    try:
        from app.services.stores.bundle import resolve_source_stores

        resolve_source_stores.cache_clear()
    except Exception:
        pass
    try:
        from app.services.stores.provider_factory import get_vector_provider

        get_vector_provider.cache_clear()
    except Exception:
        pass


def _wipe_milvus_source(milvus, source_id: str) -> None:
    for spec in COLLECTIONS:
        try:
            milvus.delete_source(spec.name, source_id)
        except Exception:
            pass


def import_and_rebuild(src: str, dest_root: str, source_id: str) -> ImportReport:
    _status(source_id, status="running", message="Importing skills folder...")
    try:
        milvus = _require_milvus()
        _wipe_milvus_source(milvus, source_id)
        report = import_skills_folder(Path(src), Path(dest_root), source_id, milvus)
        _clear_provider_caches()
        _status(
            source_id,
            status="error" if report.errors else "completed",
            message=_report_message(report),
            objects=report.objects,
            groups=report.groups,
            qas=report.qas,
            errors=report.errors,
        )
        return report
    except Exception as exc:
        _status(source_id, status="error", message=str(exc))
        raise


def rebuild_source(folder: str, source_id: str) -> ImportReport:
    folder_path = Path(folder)
    _status(source_id, status="running", message=f"Rebuilding from {folder_path.name}...")
    try:
        milvus = _require_milvus()
        _status(source_id, status="running", message="Writing vectors to Milvus...")
        _wipe_milvus_source(milvus, source_id)
        report = rebuild_vectors_from_folder(folder_path, source_id, milvus)
        _clear_provider_caches()
        _status(
            source_id,
            status="error" if report.errors else "completed",
            message=_report_message(report, folder_path.name),
            objects=report.objects,
            groups=report.groups,
            qas=report.qas,
            folder=str(folder_path),
            errors=report.errors,
        )
        return report
    except Exception as exc:
        _status(source_id, status="error", message=str(exc))
        raise


def run_rebuild(source_id: str, folder_path: Optional[str] = None) -> ImportReport:
    folder = Path(folder_path) if folder_path else resolve_data_source_folder(source_id)
    return rebuild_source(str(folder), source_id)


def start_rebuild(source_id: str, folder_path: Optional[str] = None) -> Dict[str, Any]:
    current = get_rebuild_status(source_id)
    if current.get("status") == "running":
        raise RuntimeError(f"Reload already running for {source_id}")
    folder = Path(folder_path) if folder_path else resolve_data_source_folder(source_id)
    if not folder.exists():
        raise FileNotFoundError(f"Skills folder not found: {folder}")
    return _status(
        source_id,
        status="running",
        message=f"Queued reload from {folder.name}...",
        folder=str(folder),
        objects=0,
        groups=0,
        qas=0,
        errors=[],
    )


def get_rebuild_status(source_id: str) -> Dict[str, Any]:
    return dict(_rebuild_status.get(source_id) or {"source_id": source_id, "status": "idle", "message": ""})


def _report_message(report: ImportReport, folder_name: str = "") -> str:
    prefix = f"Reloaded {folder_name}: " if folder_name else ""
    summary = f"{report.objects} objects, {report.groups} groups, {report.qas} Q&As"
    if report.errors:
        return f"{prefix}{summary} ({len(report.errors)} error(s))"
    return f"{prefix}{summary}"
