"""Resolve source_id via the data-source registry. Unknown → not found."""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException


def resolve_known_source_id(source_id: Optional[str], required: bool = False) -> Optional[str]:
    if not source_id:
        if required:
            raise HTTPException(status_code=400, detail="source_id is required")
        return None
    try:
        from app.core.user_database import get_user_db_session
        from app.services.data_source_registry_service import DataSourceRegistryService

        with get_user_db_session() as db:
            registry = DataSourceRegistryService(db)
            resolved = registry.resolve_source_id(source_id)
            if resolved:
                return resolved
            entry = registry.find_by_source_id(source_id)
            if entry and getattr(entry, "deleted_at", None) is None:
                return entry.source_id
    except HTTPException:
        raise
    except Exception:
        # Fall back to skills index when registry is unavailable (tests)
        try:
            from app.services.skills_service import get_skills_service

            skills = get_skills_service()
            for source in skills.load_data_sources_index() or []:
                if source.source_id == source_id or (source.name or "").lower() == source_id.lower():
                    return source.source_id
        except Exception:
            pass
    raise HTTPException(status_code=404, detail="Resource not found")


def require_source_id(source_id: Optional[str]) -> str:
    """HTTP APIs that target a data source must pass a known source_id.

    Missing values used to fall through to the first skills folder (alphabetically
    JCM before Northwind). Callers must select a source instead.
    """
    trimmed = (source_id or "").strip() or None
    resolved = resolve_known_source_id(trimmed, required=True)
    if not resolved:
        raise HTTPException(status_code=400, detail="source_id is required")
    return resolved


def resolve_or_primary(source_id: Optional[str]) -> str:
    if source_id:
        return resolve_known_source_id(source_id)
    try:
        from app.services.skills_service import get_skills_service

        primary = get_skills_service().load_primary_data_source()
        if primary and primary.source_id:
            return primary.source_id
        sources = get_skills_service().load_data_sources_index() or []
        if sources and sources[0].source_id:
            return sources[0].source_id
    except Exception:
        pass
    return source_id or "default"
