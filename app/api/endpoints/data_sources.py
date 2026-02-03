"""
Data source management endpoints for multi-source schema tree.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime
import re

from app.models.schemas import (
    AddDataSourceRequest, DataSourceResponse, DataSourceListResponse,
    ConnectionTestRequest, ConnectionTestResponse, TargetDBConfigV2
)
from app.services.settings_service import load_settings, save_settings
from app.services.vector_store import get_vector_store
from app.services.skills_service import SkillsService
from app.core.auth import verify_api_key
from app.core.database import test_connection
import uuid

router = APIRouter()


@router.get("/data-sources", response_model=DataSourceListResponse)
def list_data_sources(api_key: str = Depends(verify_api_key)):
    """
    List all configured data sources.
    
    Returns data sources from both agent_settings.json AND skills/data-sources/_index.md.
    Skills-based sources are read-only and represent the current skills catalog.
    """
    try:
        settings = load_settings()
        skills_service = SkillsService()
        
        sources = []
        total_objects = 0
        
        # First, add sources from skills directory (_index.md)
        try:
            skills_sources = skills_service.load_data_sources_index()
            for skill_source in skills_sources:
                # Generate a deterministic source_id from the data source name
                source_id = f"skill_{re.sub(r'[^a-zA-Z0-9]', '_', skill_source.name.lower())}"
                
                # Count objects for this source (if indexed in vector store)
                obj_count = _get_object_count_by_name(skill_source.name)
                total_objects += obj_count
                
                # Build response for skills-based source
                sources.append(DataSourceResponse(
                    source_id=source_id,
                    friendly_name=skill_source.name,
                    description=skill_source.description,
                    keywords=skill_source.keywords,
                    server="(Defined in skills)",
                    database_name="(Defined in skills)",
                    db_type="mssql",  # Default assumption
                    enabled=skill_source.status.lower() == "active",
                    is_primary=False,  # Skills sources are not primary by default
                    object_count=obj_count,
                    last_synced=None
                ))
        except Exception as skills_error:
            # Log but don't fail if skills directory is empty/missing
            print(f"Warning: Could not load skills sources: {skills_error}")
        
        # Then, add sources from agent_settings.json (if v2 config)
        if hasattr(settings, 'data_sources'):
            for source in settings.data_sources:
                obj_count = _get_object_count(source.source_id)
                total_objects += obj_count
                sources.append(_build_source_response(
                    source, 
                    is_primary=(source.source_id == settings.primary_source_id),
                    object_count=obj_count
                ))
        elif hasattr(settings, 'target_db'):
            # Legacy v1 config - return single source wrapped in v2 format
            source = TargetDBConfigV2(
                **settings.target_db.model_dump(),
                source_id=str(uuid.uuid4()),
                enabled=True
            )
            obj_count = _get_object_count(source.source_id)
            total_objects += obj_count
            sources.append(_build_source_response(source, is_primary=True, object_count=obj_count))
        
        # Determine primary source (prefer settings-based, fallback to first skills source)
        primary_source_id = None
        if hasattr(settings, 'primary_source_id'):
            primary_source_id = settings.primary_source_id
        elif sources:
            primary_source_id = sources[0].source_id
        
        return DataSourceListResponse(
            data_sources=sources,
            primary_source_id=primary_source_id,
            total_objects=total_objects
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list data sources: {str(e)}")


@router.post("/data-sources", response_model=DataSourceResponse)
def add_data_source(request: AddDataSourceRequest, api_key: str = Depends(verify_api_key)):
    """
    Add a new data source.
    
    Steps:
    1. Test connection
    2. Encrypt connection string
    3. Generate source_id
    4. Add to configuration
    5. Save settings
    """
    try:
        # Test connection first
        test_req = ConnectionTestRequest(
            driver=request.driver,
            server=request.server,
            database=request.database_name,
            auth_type=request.auth_type,
            username=request.username,
            password=request.password,
            trust_server_certificate=request.trust_server_certificate
        )
        
        test_result = test_connection(test_req)
        if not test_result.success:
            raise HTTPException(status_code=400, detail=f"Connection test failed: {test_result.message}")
        
        # Load current settings
        settings = load_settings()
        
        # Ensure v2 format
        if not hasattr(settings, 'data_sources'):
            # Need to migrate - this shouldn't happen if migration ran on startup
            raise HTTPException(
                status_code=500, 
                detail="Configuration not migrated to v2 format. Please restart the application."
            )
        
        # Build connection string and encrypt it
        from app.services.settings_service import build_connection_string, encrypt_connection_string
        
        conn_str = build_connection_string(
            db_type=request.db_type if hasattr(request, 'db_type') else "mssql",
            driver=request.driver,
            server=request.server,
            database=request.database_name,
            auth_type=request.auth_type,
            username=request.username,
            password=request.password,
            trust_server_certificate=request.trust_server_certificate
        )
        
        encrypted_conn_str = encrypt_connection_string(conn_str)
        
        # Generate source_id
        source_id = str(uuid.uuid4())
        
        # Create new source config
        new_source = TargetDBConfigV2(
            source_id=source_id,
            friendly_name=request.friendly_name,
            description=request.description,
            keywords=request.keywords,
            db_type="mssql",
            server=request.server,
            database_name=request.database_name,
            connection_string_encrypted=encrypted_conn_str,
            driver=request.driver,
            auth_type=request.auth_type,
            username=request.username,
            trust_server_certificate=request.trust_server_certificate,
            enabled=True,
            last_synced=None,
            object_count=0
        )
        
        # Add to settings
        settings.data_sources.append(new_source)
        
        # If this is the first source, set it as primary
        if settings.primary_source_id is None:
            settings.primary_source_id = source_id
        
        # Save settings
        save_settings(settings)
        
        return _build_source_response(new_source, is_primary=(source_id == settings.primary_source_id))
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add data source: {str(e)}")


@router.get("/data-sources/{source_id}", response_model=DataSourceResponse)
def get_data_source(source_id: str, api_key: str = Depends(verify_api_key)):
    """Get details of a specific data source."""
    try:
        settings = load_settings()
        
        if not hasattr(settings, 'data_sources'):
            raise HTTPException(status_code=404, detail="Data source not found (v1 configuration)")
        
        source = next((s for s in settings.data_sources if s.source_id == source_id), None)
        if not source:
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
        
        return _build_source_response(
            source,
            is_primary=(source_id == settings.primary_source_id),
            object_count=_get_object_count(source_id)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get data source: {str(e)}")


@router.put("/data-sources/{source_id}", response_model=DataSourceResponse)
def update_data_source(source_id: str, request: AddDataSourceRequest, api_key: str = Depends(verify_api_key)):
    """Update an existing data source."""
    try:
        settings = load_settings()
        
        if not hasattr(settings, 'data_sources'):
            raise HTTPException(status_code=404, detail="Data source not found (v1 configuration)")
        
        # Find source
        source_index = next((i for i, s in enumerate(settings.data_sources) if s.source_id == source_id), None)
        if source_index is None:
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
        
        existing_source = settings.data_sources[source_index]
        
        # If connection details changed, test new connection
        if (request.server != existing_source.server or 
            request.database_name != existing_source.database_name or
            request.password is not None):
            
            test_req = ConnectionTestRequest(
                driver=request.driver,
                server=request.server,
                database=request.database_name,
                auth_type=request.auth_type,
                username=request.username,
                password=request.password,
                trust_server_certificate=request.trust_server_certificate
            )
            
            test_result = test_connection(test_req)
            if not test_result.success:
                raise HTTPException(status_code=400, detail=f"Connection test failed: {test_result.message}")
            
            # Rebuild and encrypt connection string
            from app.services.settings_service import build_connection_string, encrypt_connection_string
            
            conn_str = build_connection_string(
                db_type="mssql",
                driver=request.driver,
                server=request.server,
                database=request.database_name,
                auth_type=request.auth_type,
                username=request.username,
                password=request.password,
                trust_server_certificate=request.trust_server_certificate
            )
            
            existing_source.connection_string_encrypted = encrypt_connection_string(conn_str)
        
        # Update fields
        existing_source.friendly_name = request.friendly_name
        existing_source.description = request.description
        existing_source.keywords = request.keywords
        existing_source.server = request.server
        existing_source.database_name = request.database_name
        existing_source.driver = request.driver
        existing_source.auth_type = request.auth_type
        existing_source.username = request.username
        existing_source.trust_server_certificate = request.trust_server_certificate
        
        # Save
        settings.data_sources[source_index] = existing_source
        save_settings(settings)
        
        return _build_source_response(
            existing_source,
            is_primary=(source_id == settings.primary_source_id),
            object_count=_get_object_count(source_id)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update data source: {str(e)}")


@router.delete("/data-sources/{source_id}")
def delete_data_source(source_id: str, api_key: str = Depends(verify_api_key)):
    """
    Delete a data source.
    
    This will also remove all associated objects from the vector store.
    """
    try:
        settings = load_settings()
        
        if not hasattr(settings, 'data_sources'):
            raise HTTPException(status_code=404, detail="Data source not found (v1 configuration)")
        
        # Find source
        source_index = next((i for i, s in enumerate(settings.data_sources) if s.source_id == source_id), None)
        if source_index is None:
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
        
        # Cannot delete primary source if there are other sources
        if source_id == settings.primary_source_id and len(settings.data_sources) > 1:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete primary data source. Set another source as primary first."
            )
        
        # Remove from settings
        settings.data_sources.pop(source_index)
        
        # Update primary if needed
        if source_id == settings.primary_source_id:
            settings.primary_source_id = settings.data_sources[0].source_id if settings.data_sources else None
        
        # Save settings
        save_settings(settings)
        
        # Remove from vector store
        try:
            vector_store = get_vector_store()
            vector_store.clear_source_objects_v2(source_id)
        except Exception as e:
            print(f"Warning: Failed to clear vector store objects for {source_id}: {e}")
        
        return {"status": "success", "message": f"Data source {source_id} deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete data source: {str(e)}")


@router.post("/data-sources/{source_id}/test", response_model=ConnectionTestResponse)
def test_data_source_connection(source_id: str, api_key: str = Depends(verify_api_key)):
    """Test connection to a data source."""
    try:
        settings = load_settings()
        
        if not hasattr(settings, 'data_sources'):
            raise HTTPException(status_code=404, detail="Data source not found (v1 configuration)")
        
        source = next((s for s in settings.data_sources if s.source_id == source_id), None)
        if not source:
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
        
        # Build connection test request
        from app.services.settings_service import decrypt_connection_string
        
        # Decrypt connection string to extract password
        conn_str = decrypt_connection_string(source.connection_string_encrypted)
        
        # Extract password from connection string (simple parsing)
        password = None
        if "PWD=" in conn_str:
            password = conn_str.split("PWD=")[1].split(";")[0]
        
        test_req = ConnectionTestRequest(
            driver=source.driver,
            server=source.server,
            database=source.database_name,
            auth_type=source.auth_type,
            username=source.username,
            password=password,
            trust_server_certificate=source.trust_server_certificate
        )
        
        return test_connection(test_req)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test connection: {str(e)}")


@router.post("/data-sources/{source_id}/enable")
def toggle_data_source(source_id: str, enabled: bool = True, api_key: str = Depends(verify_api_key)):
    """Enable or disable a data source."""
    try:
        settings = load_settings()
        
        if not hasattr(settings, 'data_sources'):
            raise HTTPException(status_code=404, detail="Data source not found (v1 configuration)")
        
        source = next((s for s in settings.data_sources if s.source_id == source_id), None)
        if not source:
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
        
        source.enabled = enabled
        save_settings(settings)
        
        status_text = "enabled" if enabled else "disabled"
        return {"status": "success", "message": f"Data source {status_text}"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to toggle data source: {str(e)}")


@router.post("/data-sources/{source_id}/set-primary")
def set_primary_data_source(source_id: str, api_key: str = Depends(verify_api_key)):
    """Set a data source as the primary (default) source for queries."""
    try:
        settings = load_settings()
        
        if not hasattr(settings, 'data_sources'):
            raise HTTPException(status_code=404, detail="Data source not found (v1 configuration)")
        
        source = next((s for s in settings.data_sources if s.source_id == source_id), None)
        if not source:
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
        
        settings.primary_source_id = source_id
        save_settings(settings)
        
        return {"status": "success", "message": f"Data source set as primary"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set primary source: {str(e)}")


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
    Get count of indexed objects for a data source by name.
    
    This searches the vector store for objects that match the data source name
    (e.g., "Northwind" matches schema descriptions with "Northwind").
    """
    try:
        vector_store = get_vector_store()
        # Get all schemas and filter by data source name
        all_schemas = vector_store.get_all_schemas()
        
        # Count schemas that mention this data source name
        # (This is a simple heuristic - could be improved with better metadata)
        count = sum(
            1 for schema in all_schemas 
            if data_source_name.lower() in (schema.description or "").lower() or
               data_source_name.lower() in schema.table_name.lower()
        )
        return count
    except Exception as e:
        print(f"Error counting objects for {data_source_name}: {e}")
        return 0
