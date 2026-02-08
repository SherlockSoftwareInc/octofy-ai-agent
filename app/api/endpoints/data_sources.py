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
                    server="(Defined in schema library)",
                    database_name="(Defined in schema library)",
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
    raise HTTPException(
        status_code=409,
        detail="Data sources are managed via the skills library. Configuration comes from .env file."
    )


@router.get("/data-sources/{source_id}", response_model=DataSourceResponse)
def get_data_source(source_id: str, api_key: str = Depends(verify_api_key)):
    """Get details of a specific data source."""
    try:
        skills_service = SkillsService()
        skills_sources = skills_service.load_data_sources_index()
        for skill_source in skills_sources:
            skill_source_id = f"skill_{re.sub(r'[^a-zA-Z0-9]', '_', skill_source.name.lower())}"
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
def update_data_source(source_id: str, request: AddDataSourceRequest, api_key: str = Depends(verify_api_key)):
    """Update an existing data source."""
    raise HTTPException(
        status_code=409,
        detail="Data sources are managed via the skills library. Configuration comes from .env file."
    )


@router.delete("/data-sources/{source_id}")
def delete_data_source(source_id: str, api_key: str = Depends(verify_api_key)):
    """
    Delete a data source.
    
    This will also remove all associated objects from the vector store.
    """
    raise HTTPException(
        status_code=409,
        detail="Data sources are managed via the skills library. Configuration comes from .env file."
    )


@router.post("/data-sources/{source_id}/test", response_model=ConnectionTestResponse)
def test_data_source_connection(source_id: str, api_key: str = Depends(verify_api_key)):
    """Test connection to a data source."""
    raise HTTPException(
        status_code=409,
        detail="Data sources are managed via the skills library. Configuration comes from .env file."
    )


@router.post("/data-sources/{source_id}/enable")
def toggle_data_source(source_id: str, enabled: bool = True, api_key: str = Depends(verify_api_key)):
    """Enable or disable a data source."""
    raise HTTPException(
        status_code=409,
        detail="Data sources are managed via the skills library. Configuration comes from .env file."
    )


@router.post("/data-sources/{source_id}/set-primary")
def set_primary_data_source(source_id: str, api_key: str = Depends(verify_api_key)):
    """Set a data source as the primary (default) source for queries."""
    raise HTTPException(
        status_code=409,
        detail="Data sources are managed via the skills library. Configuration comes from .env file."
    )


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
