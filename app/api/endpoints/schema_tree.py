"""
Schema tree navigation endpoints for hierarchical data source browsing.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional

from app.models.schemas import (
    SchemaTreeNode, SchemaTreeResponse, ObjectType
)
from app.services.settings_service import load_settings
from app.services.vector_store import get_vector_store
from app.core.auth import get_current_active_admin
from app.models.user_models import User
from app.core.database import get_database_engine
from sqlalchemy import inspect

router = APIRouter()


@router.get("/schema-tree", response_model=SchemaTreeResponse)
def get_full_tree(current_user: User = Depends(get_current_active_admin)):
    """
    Get complete schema tree for all data sources.
    
    Returns hierarchical structure:
    - Data Sources (roots)
      - Schemas
        - Objects (tables, views, SPs, functions)
    """
    try:
        settings = load_settings()
        
        # Check configuration version
        if not hasattr(settings, 'data_sources'):
            # V1 config - build tree from single source
            return _build_tree_v1(settings)
        
        # V2 config - build tree from multiple sources
        return _build_tree_v2(settings)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build schema tree: {str(e)}")


@router.get("/schema-tree/{source_id}", response_model=SchemaTreeResponse)
def get_source_tree(source_id: str, include_db_inspection: bool = False, current_user: User = Depends(get_current_active_admin)):
    """
    Get schema tree for a specific data source.
    
    Args:
        source_id: Data source identifier
        include_db_inspection: If True, compare with live database to show unindexed objects
    """
    try:
        settings = load_settings()
        
        if not hasattr(settings, 'data_sources'):
            raise HTTPException(status_code=404, detail="Data source not found (v1 configuration)")
        
        source = next((s for s in settings.data_sources if s.source_id == source_id), None)
        if not source:
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
        
        # Build tree for single source
        tree = _build_source_tree(source, include_db_inspection)
        
        return SchemaTreeResponse(
            roots=[tree],
            total_sources=1,
            total_objects=_count_tree_objects(tree)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build source tree: {str(e)}")


@router.get("/schema-tree/{source_id}/schemas")
def get_schemas_in_source(source_id: str, current_user: User = Depends(get_current_active_admin)) -> List[str]:
    """Get list of schema names in a data source."""
    try:
        settings = load_settings()
        
        if not hasattr(settings, 'data_sources'):
            raise HTTPException(status_code=404, detail="Data source not found")
        
        source = next((s for s in settings.data_sources if s.source_id == source_id), None)
        if not source:
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
        
        # Get schemas from vector store
        vector_store = get_vector_store()
        objects = vector_store.get_all_objects_v2(source_id=source_id)
        
        # Extract unique schema names
        schemas = sorted(set(obj.get('schema_name', 'dbo') for obj in objects))
        
        return schemas
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get schemas: {str(e)}")


@router.get("/schema-tree/{source_id}/objects")
def get_objects_in_source(
    source_id: str,
    schema_name: Optional[str] = None,
    object_type: Optional[str] = None,
    current_user: User = Depends(get_current_active_admin)
) -> List[Dict[str, Any]]:
    """
    Get objects in a data source, optionally filtered by schema and object type.
    
    Args:
        source_id: Data source identifier
        schema_name: Optional schema filter
        object_type: Optional object type filter (table, view, stored_procedure, function)
    """
    try:
        vector_store = get_vector_store()
        objects = vector_store.get_all_objects_v2(source_id=source_id)
        
        # Apply filters
        if schema_name:
            objects = [obj for obj in objects if obj.get('schema_name') == schema_name]
        
        if object_type:
            objects = [obj for obj in objects if obj.get('object_type') == object_type]
        
        return objects
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get objects: {str(e)}")


@router.post("/schema-tree/{source_id}/discover")
def discover_database_objects(
    source_id: str,
    schema_name: Optional[str] = None,
    current_user: User = Depends(get_current_active_admin)
) -> Dict[str, Any]:
    """
    Discover objects from database using database introspection.
    Returns counts by object type without adding to vector store.
    """
    try:
        settings = load_settings()
        
        if not hasattr(settings, 'data_sources'):
            raise HTTPException(status_code=404, detail="Data source not found")
        
        source = next((s for s in settings.data_sources if s.source_id == source_id), None)
        if not source:
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
        
        # Get database engine
        engine = get_database_engine(source_id)
        inspector = inspect(engine)
        
        # Discover objects
        discovered = {
            "tables": [],
            "views": [],
            "stored_procedures": [],
            "functions": []
        }
        
        schemas = [schema_name] if schema_name else inspector.get_schema_names()
        
        for schema in schemas:
            # Tables
            tables = inspector.get_table_names(schema=schema)
            discovered["tables"].extend([{"schema": schema, "name": t} for t in tables])
            
            # Views
            views = inspector.get_view_names(schema=schema)
            discovered["views"].extend([{"schema": schema, "name": v} for v in views])
        
        # Stored procedures and functions require direct SQL queries
        # This will be implemented in object_discovery_service.py
        
        return {
            "source_id": source_id,
            "schema_name": schema_name or "all",
            "discovered": discovered,
            "counts": {
                "tables": len(discovered["tables"]),
                "views": len(discovered["views"]),
                "stored_procedures": len(discovered["stored_procedures"]),
                "functions": len(discovered["functions"]),
                "total": sum(len(v) for v in discovered.values())
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to discover objects: {str(e)}")


# --- Helper Functions ---

def _build_tree_v1(settings) -> SchemaTreeResponse:
    """Build tree from v1 (single-database) configuration."""
    if not hasattr(settings, 'target_db'):
        return SchemaTreeResponse(roots=[], total_sources=0, total_objects=0)
    
    # Create temporary source node
    source_node = SchemaTreeNode(
        node_id="legacy",
        name=settings.target_db.friendly_name,
        type="source",
        metadata={
            "description": settings.target_db.description,
            "server": settings.target_db.server,
            "database": settings.target_db.database_name
        },
        is_indexed=True
    )
    
    # Get schemas from legacy collection
    vector_store = get_vector_store()
    schemas = vector_store.get_all_schemas()
    
    # Group by schema
    schema_map: Dict[str, List] = {}
    for table_schema in schemas:
        schema_name = table_schema.schema_name
        if schema_name not in schema_map:
            schema_map[schema_name] = []
        schema_map[schema_name].append(table_schema)
    
    # Build schema nodes
    for schema_name, tables in schema_map.items():
        schema_node = SchemaTreeNode(
            node_id=f"legacy:{schema_name}",
            name=schema_name,
            type="schema",
            parent_id="legacy",
            is_indexed=True
        )
        
        # Add table nodes
        for table in tables:
            table_node = SchemaTreeNode(
                node_id=f"legacy:{schema_name}:{table.table_name}",
                name=table.table_name,
                type=table.table_type or "table",
                parent_id=schema_node.node_id,
                metadata={"description": table.description},
                is_indexed=True
            )
            schema_node.children.append(table_node)
        
        source_node.children.append(schema_node)
    
    total_objects = sum(len(node.children) for node in source_node.children)
    
    return SchemaTreeResponse(
        roots=[source_node],
        total_sources=1,
        total_objects=total_objects
    )


def _build_tree_v2(settings) -> SchemaTreeResponse:
    """Build tree from v2 (multi-source) configuration."""
    vector_store = get_vector_store()
    roots = []
    total_objects = 0
    
    for source in settings.data_sources:
        source_tree = _build_source_tree(source, include_db_inspection=False)
        roots.append(source_tree)
        total_objects += _count_tree_objects(source_tree)
    
    return SchemaTreeResponse(
        roots=roots,
        total_sources=len(settings.data_sources),
        total_objects=total_objects
    )


def _build_source_tree(source, include_db_inspection: bool = False) -> SchemaTreeNode:
    """Build tree for a single data source."""
    source_node = SchemaTreeNode(
        node_id=source.source_id,
        name=source.friendly_name,
        type="source",
        metadata={
            "description": source.description,
            "server": source.server,
            "database": source.database_name,
            "enabled": source.enabled,
            "keywords": source.keywords
        },
        is_indexed=True
    )
    
    # Get objects from vector store
    vector_store = get_vector_store()
    objects = vector_store.get_all_objects_v2(source_id=source.source_id)
    
    # Group by schema
    schema_map: Dict[str, List[Dict[str, Any]]] = {}
    for obj in objects:
        schema_name = obj.get('schema_name', 'dbo')
        if schema_name not in schema_map:
            schema_map[schema_name] = []
        schema_map[schema_name].append(obj)
    
    # Build schema nodes
    for schema_name, schema_objects in sorted(schema_map.items()):
        schema_node = SchemaTreeNode(
            node_id=f"{source.source_id}:{schema_name}",
            name=schema_name,
            type="schema",
            parent_id=source.source_id,
            is_indexed=True
        )
        
        # Add object nodes
        for obj in sorted(schema_objects, key=lambda x: (x.get('object_type', ''), x.get('object_name', ''))):
            object_node = SchemaTreeNode(
                node_id=f"{source.source_id}:{schema_name}:{obj.get('object_name')}",
                name=obj.get('object_name', 'unknown'),
                type=obj.get('object_type', 'table'),
                parent_id=schema_node.node_id,
                metadata={
                    "description": obj.get('description', ''),
                    "definition": obj.get('definition'),
                    "return_type": obj.get('return_type')
                },
                is_indexed=True
            )
            schema_node.children.append(object_node)
        
        source_node.children.append(schema_node)
    
    return source_node


def _count_tree_objects(node: SchemaTreeNode) -> int:
    """Recursively count object nodes (excluding sources and schemas)."""
    if node.type not in ["source", "schema"]:
        return 1
    return sum(_count_tree_objects(child) for child in node.children)
