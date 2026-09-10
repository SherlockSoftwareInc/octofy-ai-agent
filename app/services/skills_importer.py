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


def _sync_legacy_schema_index(provider, source_id: str) -> int:
    """Write parent schema rows into Milvus schema_index / schema_index_v2 for the admin UI."""
    from app.models.schemas import ColumnInfo, DataObject, ObjectType, TableSchema
    from app.services.vector_store import get_vector_store

    vs = get_vector_store()
    if hasattr(vs, "clear_schemas_collection"):
        vs.clear_schemas_collection(source_id)
    if hasattr(vs, "clear_source_objects_v2"):
        vs.clear_source_objects_v2(source_id)

    rows = provider.fetch_all("schemas", source_id)
    parents = {}
    columns = {}
    for row in rows:
        schema_name = row.get("schema_name") or "dbo"
        object_name = row.get("object_name") or ""
        key = (schema_name, object_name)
        if (row.get("entity_type") or "") == "Column":
            columns.setdefault(key, []).append(
                ColumnInfo(
                    name=row.get("column_name") or "",
                    data_type="",
                    description=row.get("description") or "",
                )
            )
        else:
            parents[key] = row

    type_map = {
        "table": ObjectType.TABLE,
        "view": ObjectType.VIEW,
        "function": ObjectType.FUNCTION,
        "stored_procedure": ObjectType.STORED_PROCEDURE,
    }
    count = 0
    for key, row in parents.items():
        schema_name, object_name = key
        raw_type = (row.get("object_type") or "Table")
        table_type = "view" if str(raw_type).lower() == "view" else "table"
        text = row.get("description") or object_name
        cols = columns.get(key, [])
        schema = TableSchema(
            schema_name=schema_name,
            table_name=object_name,
            table_type=table_type,
            description=text[:4000],
            columns=cols,
            source_guid=source_id,
        )
        vs.insert_schema_embedding(schema, text[:4000], table_type=table_type)
        vs.insert_data_object_v2(
            DataObject(
                source_id=source_id,
                schema_name=schema_name,
                object_name=object_name,
                object_type=type_map.get(str(raw_type).lower(), ObjectType.TABLE),
                description=text[:4000],
                columns=cols,
            ),
            text[:4000],
        )
        count += 1
    return count


def import_and_rebuild(src: str, dest_root: str, source_id: str) -> ImportReport:
    _status(source_id, status="running", message="Importing skills folder...")
    try:
        milvus = _require_milvus()
        _wipe_milvus_source(milvus, source_id)
        report = import_skills_folder(Path(src), Path(dest_root), source_id, milvus)
        try:
            _sync_legacy_schema_index(milvus, source_id)
        except Exception as exc:
            report.errors.append(f"schema_index sync: {exc}")
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
        try:
            _sync_legacy_schema_index(milvus, source_id)
        except Exception as exc:
            report.errors.append(f"schema_index sync: {exc}")
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
