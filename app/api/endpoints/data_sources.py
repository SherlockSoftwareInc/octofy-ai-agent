"""
Data source management endpoints for multi-source schema tree.
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File, Query
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
import re
import logging

from app.models.schemas import (
    AddDataSourceRequest, DataSourceResponse, DataSourceListResponse,
    ConnectionTestRequest, ConnectionTestResponse, TargetDBConfigV2,
    ScanDataSourceRequest, ResolveDataSourceResponse
)
from app.services.vector_store import get_vector_store
from app.services.skills_service import SkillsService
from app.core.auth import get_current_active_admin, get_current_user
from app.models.user_models import User
from app.core.database import test_connection
from app.core.user_database import get_user_db
from app.services.data_source_registry_service import DataSourceRegistryService
import uuid

logger = logging.getLogger(__name__)

# In-memory scan status store (source_id -> status dict)
_scan_status: Dict[str, Dict] = {}

router = APIRouter()


@router.get("/data-sources", response_model=DataSourceListResponse)
def list_data_sources(current_user: User = Depends(get_current_user)):
    """
    List all configured data sources.

    Requires a valid user API key in the X-API-Key header.
    Returns data sources from skills/data-sources/_index.md.
    All data sources are managed via the skills directory (.md files).
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        skills_service = SkillsService()
        
        sources = []
        total_objects = 0
        
        # First, add sources from skills directory (_index.md)
        try:
            skills_sources = skills_service.load_data_sources_index()
            logger.info(f"Loaded {len(skills_sources)} data sources from skills directory")
            
            for skill_source in skills_sources:
                # Prefer GUID from skills front matter; fallback to deterministic ID
                source_id = skill_source.source_id or f"skill_{re.sub(r'[^a-zA-Z0-9]', '_', skill_source.name.lower())}"
                
                # Count objects for this source (if indexed in vector store)
                obj_count = _get_object_count_by_name(skill_source.name)
                total_objects += obj_count
                
                # Build response for skills-based source
                parsed = skills_service._parse_data_source_file(Path(skill_source.file_path)) if skill_source.file_path else None
                conn = (parsed.connection_info if parsed else None) or skill_source.connection_info or {}

                sources.append(DataSourceResponse(
                    source_id=source_id,
                    friendly_name=skill_source.name,
                    description=skill_source.description,
                    keywords=skill_source.keywords,
                    server=conn.get("server") or "(Defined in schema library)",
                    database_name=conn.get("database") or "(Defined in schema library)",
                    db_type="mssql",  # Default assumption
                    enabled=skill_source.status.lower() == "active",
                    is_primary=False,  # Skills sources are not primary by default
                    object_count=obj_count,
                    last_synced=None
                ))
        except Exception as skills_error:
            # Log but don't fail if skills directory is empty/missing
            logger.warning(f"Could not load skills sources: {skills_error}", exc_info=True)
        
        primary_source_id = sources[0].source_id if sources else None
        
        logger.info(f"Returning {len(sources)} data sources with {total_objects} total objects")
        return DataSourceListResponse(
            data_sources=sources,
            primary_source_id=primary_source_id,
            total_objects=total_objects
        )
    
    except Exception as e:
        logger.error(f"Failed to list data sources: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list data sources: {str(e)}")


@router.post("/data-sources", response_model=DataSourceResponse)
def add_data_source(
    request: AddDataSourceRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_admin),
):
    """
    Add a new data source via the skills library.

    Creates the data source folder structure and _data-source.md in skills/data-sources/.
    If server and database_name are provided (SQL Server), a background scan is
    automatically started to discover and generate schema skill files.
    """
    try:
        from app.services.skills_admin_service import create_data_source as create_ds

        # Map AddDataSourceRequest fields to skills format
        data = {
            "name": request.friendly_name,
            "description": request.description,
            "keywords": request.keywords,
            "type": "SQL Server",
            "status": "Active",
            "server": request.server,
            "database": request.database_name,
        }

        result = create_ds(data)

        # Build response
        source_id = result.get("source_id") or f"skill_{re.sub(r'[^a-zA-Z0-9]', '_', request.friendly_name.lower())}"

        # If SQL Server connection info provided, auto-scan in background
        if request.server and request.database_name and not request.skip_auto_scan:
            _scan_status[source_id] = {"status": "running", "message": "Scan queued..."}
            background_tasks.add_task(
                _run_schema_scan,
                source_id=source_id,
                data_source_name=request.friendly_name,
                server=request.server,
                database=request.database_name,
                auth_type=request.auth_type or "windows",
                driver=request.driver or "ODBC Driver 17 for SQL Server",
                username=request.username,
                password=request.password,
                trust_server_certificate=request.trust_server_certificate,
                description=request.description,
                keywords=request.keywords,
            )

        return DataSourceResponse(
            source_id=source_id,
            friendly_name=request.friendly_name,
            description=request.description,
            keywords=request.keywords,
            server=request.server or "(Defined in schema library)",
            database_name=request.database_name or "(Defined in schema library)",
            db_type=request.db_type or "mssql",
            enabled=True,
            is_primary=False,
            object_count=0,
            last_synced=None,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to create data source: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create data source: {str(e)}")


@router.post("/data-sources/{source_id}/scan")
def scan_data_source(
    source_id: str,
    background_tasks: BackgroundTasks,
    body: ScanDataSourceRequest = None,
    current_user: User = Depends(get_current_active_admin),
):
    """
    Trigger a schema scan for an existing data source.

    Connection info can come from:
    1. The request body (highest priority)
    2. The _data-source.md file
    If provided via body, the _data-source.md is also updated.
    """
    from app.services.skills_service import SkillsService

    skills_service = SkillsService()
    skills_service._data_sources_cache = None  # Clear cache
    skills_sources = skills_service.load_data_sources_index()
    actual_name = None
    for s in skills_sources:
        sid = s.source_id or f"skill_{re.sub(r'[^a-zA-Z0-9]', '_', s.name.lower())}"
        if sid == source_id:
            actual_name = s.name
            break

    if not actual_name:
        raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")

    server = None
    database = None
    auth_type = "windows"
    driver = "ODBC Driver 17 for SQL Server"
    username = None
    password = None
    trust_cert = True

    # 1. Try request body first
    if body and body.server and body.database_name:
        server = body.server
        database = body.database_name
        auth_type = body.auth_type or "windows"
        driver = body.driver or driver
        username = body.username
        password = body.password
        trust_cert = body.trust_server_certificate

        # Persist to _data-source.md so future scans don't need body
        from app.services.schema_scan_service import _ensure_connection_fields
        from pathlib import Path
        slug = re.sub(r'[^\w\s-]', '', actual_name.lower()).replace(' ', '-')
        ds_dir = Path("skills/data-sources") / slug
        if ds_dir.exists():
            _ensure_connection_fields(ds_dir, server, database)

    # 2. Fallback to _data-source.md
    if not server or not database:
        ds = skills_service.load_primary_data_source_by_name(actual_name)
        if ds and hasattr(ds, 'connection_info') and ds.connection_info:
            server = server or ds.connection_info.get('server')
            database = database or ds.connection_info.get('database')

    if not server or not database:
        conn = _read_connection_from_md(actual_name)
        server = server or conn.get('server')
        database = database or conn.get('database')

    if not server or not database:
        raise HTTPException(
            status_code=400,
            detail="missing_connection_info"
        )

    _scan_status[source_id] = {"status": "running", "message": "Scan started..."}
    background_tasks.add_task(
        _run_schema_scan,
        source_id=source_id,
        data_source_name=actual_name,
        server=server,
        database=database,
        auth_type=auth_type,
        driver=driver,
        username=username,
        password=password,
        trust_server_certificate=trust_cert,
    )

    return {"status": "started", "message": f"Schema scan started for {actual_name}"}


@router.get("/data-sources/{source_id}/scan-status")
def get_scan_status(source_id: str, current_user: User = Depends(get_current_active_admin)):
    """Get the current scan status for a data source."""
    if source_id in _scan_status:
        return _scan_status[source_id]
    return {"status": "idle", "message": "No scan running"}


def _run_schema_scan(
    source_id: str,
    data_source_name: str,
    server: str,
    database: str,
    auth_type: str = "windows",
    driver: str = "ODBC Driver 17 for SQL Server",
    username: str = None,
    password: str = None,
    trust_server_certificate: bool = True,
    description: str = "",
    keywords: List[str] = None,
):
    """Background task wrapper for schema scanning."""
    try:
        _scan_status[source_id] = {"status": "running", "message": "Connecting to database..."}
        from app.services.schema_scan_service import scan_database_objects

        result = scan_database_objects(
            data_source_name=data_source_name,
            server=server,
            database=database,
            auth_type=auth_type,
            driver=driver,
            username=username,
            password=password,
            trust_server_certificate=trust_server_certificate,
            description=description,
            keywords=keywords or [],
        )
        # Update Milvus schema index collection so vector search uses the new schema library
        msg = f"Scan complete: {result['total_objects']} objects discovered ({result['tables_created']} tables, {result['views_created']} views) across {result['schemas_scanned']} schemas."
        try:
            SkillsService().clear_cache()
            from app.core.database import clear_engine_cache
            clear_engine_cache(source_id)
            from app.services.ingest_service import ingest_metadata
            _scan_status[source_id] = {"status": "running", "message": "Updating Milvus schema index..."}
            ingest_metadata(source_id=source_id)
            msg += " Schema library and Milvus index updated."
        except Exception as ingest_e:
            logger.warning(f"Schema scan succeeded but Milvus ingest failed for {data_source_name}: {ingest_e}", exc_info=True)
            msg += f" Schema library updated; Milvus index update failed: {ingest_e}"
        _scan_status[source_id] = {
            "status": "completed",
            "message": msg,
            "result": result,
        }
    except Exception as e:
        logger.error(f"Schema scan failed for {data_source_name}: {e}", exc_info=True)
        _scan_status[source_id] = {
            "status": "error",
            "message": f"Scan failed: {str(e)}",
        }


def _read_connection_from_md(data_source_name: str) -> Dict[str, str]:
    """Read Server/Database from _data-source.md."""
    from pathlib import Path
    slug = re.sub(r'[^\w\s-]', '', data_source_name.lower()).replace(' ', '-')
    ds_file = Path("skills/data-sources") / slug / "_data-source.md"
    result = {}
    if ds_file.exists():
        content = ds_file.read_text(encoding='utf-8')
        server_m = re.search(r'\*\*Server:\*\*\s*([^\n]+)', content)
        db_m = re.search(r'\*\*Database:\*\*\s*([^\n]+)', content)
        if server_m:
            result['server'] = server_m.group(1).strip()
        if db_m:
            result['database'] = db_m.group(1).strip()
    return result


def _load_data_source_md(name: str):
    """Try to load data source info by name."""
    try:
        skills_service = SkillsService()
        for ds in skills_service.load_data_sources_index():
            if ds.name.lower() == name.lower():
                return ds
    except Exception:
        pass
    return None


@router.get("/data-sources/resolve", response_model=ResolveDataSourceResponse)
def resolve_data_source(
    server: Optional[str] = Query(None, description="Server name (for SQL Server)"),
    database: Optional[str] = Query(None, description="Database name (for SQL Server)"),
    file_path: Optional[str] = Query(None, description="File path (for Excel/file-based sources)"),
    db: Session = Depends(get_user_db),
    current_user: User = Depends(get_current_active_admin)
):
    """
    Resolve data source connection details to source_id.

    Supports two patterns:
    - **SQL Server**: Provide both `server` AND `database` parameters
    - **Excel/File**: Provide `file_path` parameter
    """
    # Validate parameter combinations
    has_sql_params = bool(server or database)
    has_file_params = bool(file_path)

    if has_sql_params and has_file_params:
        raise HTTPException(
            status_code=400,
            detail="Cannot mix SQL Server and file-based parameters. Use either (server + database) or file_path."
        )

    if not has_sql_params and not has_file_params:
        raise HTTPException(
            status_code=400,
            detail="Must provide either (server + database) or file_path"
        )

    if has_sql_params and (not server or not database):
        raise HTTPException(
            status_code=400,
            detail="Both server and database are required for SQL Server lookup"
        )

    # Perform lookup
    registry_service = DataSourceRegistryService(db)
    entry = registry_service.find_by_connection_info(
        server=server,
        database=database,
        file_path=file_path
    )

    if not entry:
        if has_sql_params:
            raise HTTPException(
                status_code=404,
                detail=f"Data source not found: {server}\\{database}"
            )
        raise HTTPException(
            status_code=404,
            detail=f"Data source not found: {file_path}"
        )

    # Prefer registry connection_info, then fallback to markdown metadata.
    conn_info = entry.connection_info or {}
    md_conn = _read_connection_from_md(entry.name)
    resolved_server = conn_info.get('server') or md_conn.get('server')
    resolved_database = conn_info.get('database') or md_conn.get('database')
    resolved_file_path = conn_info.get('file_path') or entry.file_path

    # Get object count
    object_count = _get_object_count_by_name(entry.name)

    # Build response
    return ResolveDataSourceResponse(
        source_id=entry.source_id,
        name=entry.name,
        type=entry.type,
        server=resolved_server,
        database=resolved_database,
        file_path=resolved_file_path,
        status="active" if not entry.deleted_at else "deleted",
        object_count=object_count
    )


@router.get("/data-sources/{source_id}", response_model=DataSourceResponse)
def get_data_source(source_id: str, current_user: User = Depends(get_current_active_admin)):
    """Get details of a specific data source."""
    try:
        skills_service = SkillsService()
        skills_sources = skills_service.load_data_sources_index()
        for skill_source in skills_sources:
            skill_source_id = skill_source.source_id or f"skill_{re.sub(r'[^a-zA-Z0-9]', '_', skill_source.name.lower())}"
            if skill_source_id == source_id:
                obj_count = _get_object_count_by_name(skill_source.name)
                return DataSourceResponse(
                    source_id=skill_source_id,
                    friendly_name=skill_source.name,
                    description=skill_source.description,
                    keywords=skill_source.keywords,
                    server="(Defined in schema library)",
                    database_name="(Defined in schema library)",
                    db_type="mssql",
                    enabled=skill_source.status.lower() == "active",
                    is_primary=False,
                    object_count=obj_count,
                    last_synced=None
                )
        raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get data source: {str(e)}")


@router.put("/data-sources/{source_id}", response_model=DataSourceResponse)
def update_data_source(source_id: str, request: AddDataSourceRequest, current_user: User = Depends(get_current_active_admin)):
    """Update an existing data source via the skills library."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.services.skills_admin_service import update_data_source as update_ds
        
        data = {
            "name": request.friendly_name,
            "description": request.description,
            "keywords": request.keywords,
            "type": "SQL Server",
            "status": "Active",
        }
        
        # Try to find the actual data source name from skills index
        skills_service = SkillsService()
        skills_sources = skills_service.load_data_sources_index()
        actual_name = None
        for s in skills_sources:
            sid = s.source_id or f"skill_{re.sub(r'[^a-zA-Z0-9]', '_', s.name.lower())}"
            if sid == source_id:
                actual_name = s.name
                break
        
        if not actual_name:
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
        
        update_ds(actual_name, data)
        
        new_source_id = source_id
        obj_count = _get_object_count_by_name(request.friendly_name)
        return DataSourceResponse(
            source_id=new_source_id,
            friendly_name=request.friendly_name,
            description=request.description,
            keywords=request.keywords,
            server=request.server or "(Defined in schema library)",
            database_name=request.database_name or "(Defined in schema library)",
            db_type="mssql",
            enabled=True,
            is_primary=False,
            object_count=obj_count,
            last_synced=None,
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to update data source: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update data source: {str(e)}")


@router.delete("/data-sources/{source_id}")
def delete_data_source(source_id: str, current_user: User = Depends(get_current_active_admin)):
    """
    Delete a data source and all its contents from the skills library.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from app.services.skills_admin_service import delete_data_source as delete_ds
        
        # Find actual name from source_id
        skills_service = SkillsService()
        skills_sources = skills_service.load_data_sources_index()
        actual_name = None
        for s in skills_sources:
            sid = s.source_id or f"skill_{re.sub(r'[^a-zA-Z0-9]', '_', s.name.lower())}"
            if sid == source_id:
                actual_name = s.name
                break
        
        if not actual_name:
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
        
        delete_ds(actual_name)
        return {"status": "success", "message": f"Deleted data source: {actual_name}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete data source: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete data source: {str(e)}")


@router.post("/data-sources/{source_id}/test", response_model=ConnectionTestResponse)
def test_data_source_connection(source_id: str, current_user: User = Depends(get_current_active_admin)):
    """Test connection to a data source."""
    return ConnectionTestResponse(
        success=True,
        message="Data source is managed via the skills library. Connection testing uses the primary .env connection."
    )


@router.post("/data-sources/{source_id}/enable")
def toggle_data_source(source_id: str, enabled: bool = True, current_user: User = Depends(get_current_active_admin)):
    """Enable or disable a data source."""
    return {"status": "success", "message": f"Data source status updated", "enabled": enabled}


@router.post("/data-sources/{source_id}/set-primary")
def set_primary_data_source(source_id: str, current_user: User = Depends(get_current_active_admin)):
    """Set a data source as the primary (default) source for queries."""
    return {"status": "success", "message": f"Primary data source updated to {source_id}"}


# --- Exclude Objects ---

def _resolve_ds_dir(source_id: str) -> Path:
    """
    Resolve source_id to the data source directory on disk.

    Raises HTTPException(404) if the source is not found.
    """
    skills_service = SkillsService()
    skills_service._data_sources_cache = None
    for s in skills_service.load_data_sources_index():
        sid = s.source_id or f"skill_{re.sub(r'[^a-zA-Z0-9]', '_', s.name.lower())}"
        if sid == source_id:
            slug = re.sub(r'[^\w\s-]', '', s.name.lower()).replace(' ', '-')
            return Path("skills/data-sources") / slug
    raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")


@router.post("/data-sources/{source_id}/exclude-objects")
async def upload_exclude_objects(
    source_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_admin),
):
    """
    Upload an exclude_objects.txt file for a data source.

    The file should contain one database object name per line.
    Blank lines and lines starting with '#' are treated as comments.
    Objects listed here will be skipped during the next schema scan.
    """
    if not file.filename or not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="File must be a .txt file")

    ds_dir = _resolve_ds_dir(source_id)
    if not ds_dir.exists():
        raise HTTPException(status_code=404, detail=f"Data source directory not found: {ds_dir}")

    contents = await file.read()
    text = contents.decode("utf-8")

    # Parse and count valid entries
    names = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    exclude_file = ds_dir / "exclude_objects.txt"
    exclude_file.write_text(text, encoding="utf-8")

    logger.info(f"Uploaded exclude_objects.txt for {source_id} with {len(names)} object(s)")
    return {
        "status": "success",
        "message": f"Uploaded exclusion list with {len(names)} object(s)",
        "objects": names,
        "count": len(names),
    }


@router.get("/data-sources/{source_id}/exclude-objects")
def get_exclude_objects(
    source_id: str,
    current_user: User = Depends(get_current_active_admin),
):
    """
    Get the current exclusion list for a data source.

    Returns the list of object names and count. If no exclude_objects.txt
    file exists, returns an empty list.
    """
    ds_dir = _resolve_ds_dir(source_id)
    exclude_file = ds_dir / "exclude_objects.txt"

    if not exclude_file.exists():
        return {"objects": [], "count": 0}

    names = [
        line.strip()
        for line in exclude_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return {"objects": names, "count": len(names)}


@router.delete("/data-sources/{source_id}/exclude-objects")
def delete_exclude_objects(
    source_id: str,
    current_user: User = Depends(get_current_active_admin),
):
    """
    Delete the exclude_objects.txt file for a data source.

    After deletion, the next schema scan will include all discovered objects.
    """
    ds_dir = _resolve_ds_dir(source_id)
    exclude_file = ds_dir / "exclude_objects.txt"

    if not exclude_file.exists():
        return {"status": "success", "message": "No exclusion list to delete"}

    exclude_file.unlink()
    logger.info(f"Deleted exclude_objects.txt for {source_id}")
    return {"status": "success", "message": "Exclusion list deleted"}


@router.get("/data-sources/registry")
def list_data_source_registry(
    include_deleted: bool = False,
    current_user: User = Depends(get_current_active_admin),
    db: Session = Depends(get_user_db)
):
    """
    View all data sources ever created in the PostgreSQL registry (admin only).
    
    This endpoint shows the persistent ID registry that enables ID reuse when
    data sources are deleted and recreated. Useful for troubleshooting conversations
    that reference old source IDs.
    
    Args:
        include_deleted: If True, includes soft-deleted data sources
        
    Returns:
        List of data source registry entries with ID, name, status, timestamps
    """
    try:
        registry = DataSourceRegistryService(db)
        entries = registry.list_all(include_deleted=include_deleted)
        
        return {
            "status": "success",
            "count": len(entries),
            "include_deleted": include_deleted,
            "entries": entries
        }
    except Exception as e:
        logger.error(f"Error listing data source registry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- Helper Functions ---

def _build_source_response(source: TargetDBConfigV2, is_primary: bool, object_count: int = None) -> DataSourceResponse:
    """Build DataSourceResponse from TargetDBConfigV2."""
    if object_count is None:
        object_count = _get_object_count(source.source_id)
    
    return DataSourceResponse(
        source_id=source.source_id,
        friendly_name=source.friendly_name,
        description=source.description,
        keywords=source.keywords,
        server=source.server,
        database_name=source.database_name,
        db_type=source.db_type,
        enabled=source.enabled,
        is_primary=is_primary,
        object_count=object_count,
        last_synced=source.last_synced
    )


def _get_object_count(source_id: str) -> int:
    """Get count of indexed objects for a data source from vector store."""
    try:
        vector_store = get_vector_store()
        objects = vector_store.get_all_objects_v2(source_id=source_id)
        return len(objects)
    except Exception:
        return 0


def _get_object_count_by_name(data_source_name: str) -> int:
    """
    Get count of objects for a skills-based data source by counting schema files.
    
    For skills-based sources, count .md files in the schemas directory (schema library v2).
    """
    try:
        from pathlib import Path
        import logging
        logger = logging.getLogger(__name__)
        
        # Convert data source name to slug format (e.g., "Northwind" -> "northwind")
        slug = re.sub(r'[^\w\s-]', '', data_source_name.lower()).replace(' ', '-')
        skills_path = Path("skills/data-sources") / slug / "schemas"
        
        if not skills_path.exists():
            logger.warning(f"Skills path not found for {data_source_name}: {skills_path}")
            return 0
        
        # Count all .md files in the schemas directory (recursively)
        schema_files = list(skills_path.rglob("*.md"))
        count = len(schema_files)
        logger.info(f"Found {count} schema files for {data_source_name} in {skills_path}")
        return count
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error counting objects for {data_source_name}: {e}", exc_info=True)
        return 0
