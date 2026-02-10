from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse, FileResponse
from typing import List, Dict, Optional
from app.models.schemas import (
    AdminSchemaStatus, FewShotItem, ValueIndexItem, BatchSyncRequest, BatchSyncResponse, 
    EnhanceSchemaRequest, EnhanceSchemaResponse, AddObjectRequest, SyncObjectRequest,
    DiscoverObjectsRequest, DiscoverObjectsResponse, DataObject, ObjectType
)
from app.services.admin_service import (
    get_schema_status, sync_specific_table, sync_all_schemas, batch_sync_tables,
    ingest_values_from_excel, get_all_values, delete_value_item, clear_all_values,
    ingest_schemas_from_excel, ingest_fewshots_from_excel
)
from app.services.skills_service import get_skills_service
from app.services.vector_store import get_vector_store
from app.core.auth import get_current_active_admin
from app.models.user_models import User
import json
import asyncio
import os
import tempfile
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Global state for tracking upload progress
_upload_progress = {"current": 0, "total": 0, "status": "idle"}

# --- Schema Management ---

@router.get("/schema/status", response_model=List[AdminSchemaStatus])
def get_schemas_status(include_db_inspection: bool = False, current_user: User = Depends(get_current_active_admin)):
    """Get status of all schemas in database vs vector store
    
    Args:
        include_db_inspection: If True, compare with database to show missing tables.
                              If False (default), only return indexed schemas for faster loading.
    """
    try:
        return get_schema_status(include_database_inspection=include_db_inspection)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/schema/sync")
def sync_table(schema: str, table: str, current_user: User = Depends(get_current_active_admin)):
    try:
        success = sync_specific_table(schema, table)
        return {"status": "success", "message": f"Synced {schema}.{table}"}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/schema/sync-full")
def sync_all(current_user: User = Depends(get_current_active_admin)):
    try:
        sync_all_schemas()
        return {"status": "success", "message": "Successfully synced all schemas and rebuilt vector index"}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/schema/batch-sync", response_model=BatchSyncResponse)
def batch_sync(request: BatchSyncRequest, current_user: User = Depends(get_current_active_admin)):
    """
    Batch sync multiple tables from database to vector store.
    
    Accepts a list of table names in the format:
    - 'TableName' (uses default schema 'dbo')
    - 'schema.TableName' (explicit schema)
    
    Returns detailed results for each table including success/failure status.
    """
    try:
        if not request.table_names:
            raise HTTPException(status_code=400, detail="table_names list cannot be empty")
        
        result = batch_sync_tables(request.table_names, source_id=request.source_id)
        return BatchSyncResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/schema/description")
def update_schema_description(schema: str, table: str, description: str, current_user: User = Depends(get_current_active_admin)):
    try:
        vector_store = get_vector_store()
        vector_store.update_schema_description(schema, table, description)
        return {"status": "success", "message": f"Updated description for {schema}.{table}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/schema")
def delete_schema(schema: str, table: str, current_user: User = Depends(get_current_active_admin)):
    try:
        vector_store = get_vector_store()
        vector_store.delete_schema(schema, table)
        return {"status": "success", "message": f"Deleted {schema}.{table} from vector store"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schema/export")
def export_schemas(current_user: User = Depends(get_current_active_admin)):
    """
    Export all schemas from the vector store to an Excel file.
    """
    from pandas import DataFrame
    import json as json_module
    
    try:
        vector_store = get_vector_store()
        schemas = vector_store.get_all_schemas()
        
        # Prepare data for export (exclude embeddings)
        # schemas are TableSchema objects, not dicts
        # Columns match the Milvus schema_index collection: schema_name, table_name, table_type, description
        export_data = []
        for schema in schemas:
            export_data.append({
                'schema_name': schema.schema_name,
                'table_name': schema.table_name,
                'table_type': schema.table_type or 'table',
                'description': schema.description or ''
            })
        
        df = DataFrame(export_data)
        
        # Create temp file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_path = os.path.join(tempfile.gettempdir(), f'schema_index_{timestamp}.xlsx')
        df.to_excel(temp_path, index=False)
        
        return FileResponse(
            temp_path,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename=f'schema_index_{timestamp}.xlsx'
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting schemas: {str(e)}")

@router.post("/ingest-schemas")
async def ingest_schemas(file: UploadFile = File(...), mode: str = Form("append"), source_id: Optional[str] = Form(None), current_user: User = Depends(get_current_active_admin)):
    """
    Upload an Excel file to ingest schema/table metadata.
    
    File format required:
    - Column 1: schema_name (e.g., 'dbo')
    - Column 2: table_name (e.g., 'Customers')
    - Column 3: description (table description)
    """
    global _upload_progress
    
    try:
        if not source_id:
            raise HTTPException(status_code=400, detail="A data source must be selected before uploading. Please select a data source and try again.")
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="File must be Excel format (.xlsx or .xls)")
        
        contents = await file.read()
        
        # Initialize progress tracking
        _upload_progress = {"current": 0, "total": 0, "status": "processing"}
        
        # Give frontend time to establish SSE connection (200ms)
        await asyncio.sleep(0.2)
        
        # Define progress callback
        def progress_callback(current: int, total: int):
            global _upload_progress
            _upload_progress = {"current": current, "total": total, "status": "processing"}
        
        result = ingest_schemas_from_excel(contents, mode, progress_callback, source_id=source_id)
        
        # Mark as complete
        _upload_progress = {"current": result.get("rows_processed", 0), "total": result.get("total_rows", 0), "status": "complete"}
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        _upload_progress = {"current": 0, "total": 0, "status": "error"}
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@router.get("/schema/template")
def get_schema_template(current_user: User = Depends(get_current_active_admin)):
    """
    Download a template Excel file for schema ingestion.
    """
    from pandas import DataFrame
    
    # Create template DataFrame
    template_data = {
        'schema_name': ['dbo', 'dbo', 'Sales'],
        'table_name': ['Customers', 'Orders', 'Invoices'],
        'description': ['Contains customer information', 'Order headers and details', 'Sales invoices and payments']
    }
    
    df = DataFrame(template_data)
    
    # Save to temporary file
    temp_path = os.path.join(tempfile.gettempdir(), 'schema_import_template.xlsx')
    df.to_excel(temp_path, index=False)
    
    return FileResponse(
        temp_path,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        filename='schema_import_template.xlsx'
    )

@router.post("/schema/clear")
def clear_all_schemas_endpoint(current_user: User = Depends(get_current_active_admin)):
    """
    Clear all schemas from the vector store.
    """
    try:
        from app.services.admin_service import clear_all_schemas_data
        success = clear_all_schemas_data()
        if success:
            return {"status": "success", "message": "Cleared all schemas from vector store"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear schemas")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Multi-Source Object Management (V2) ---

@router.post("/object")
def add_data_object(request: AddObjectRequest, current_user: User = Depends(get_current_active_admin)):
    """
    Add a data object (table, view, SP, function) to vector store.
    
    This manually adds an object without discovering from database.
    """
    try:
        vector_store = get_vector_store()
        
        # Create DataObject
        obj = DataObject(
            source_id=request.source_id,
            schema_name=request.schema_name,
            object_name=request.object_name,
            object_type=request.object_type,
            description=request.description or f"{request.object_type.value}: {request.object_name}",
            columns=[]
        )
        
        # Generate embedding text
        embedding_text = f"{obj.object_name} {obj.description}"
        
        # Insert to vector store
        vector_store.insert_data_object_v2(obj, embedding_text)
        
        return {"status": "success", "message": f"Added {obj.object_name} to vector store"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add object: {str(e)}")


@router.post("/object/sync")
def sync_data_object(request: SyncObjectRequest, current_user: User = Depends(get_current_active_admin)):
    """
    Sync a specific object from database to vector store.
    
    Discovers the object from database and adds it to vector store with full metadata.
    """
    try:
        from app.core.database import get_database_engine
        from app.services.object_discovery_service import (
            discover_stored_procedures, discover_functions,
            build_sp_markdown_description, build_function_markdown_description
        )
        from app.services.ingest_service import build_table_markdown_description
        from sqlalchemy import inspect
        
        # Get database engine
        engine = get_database_engine(request.source_id)
        inspector = inspect(engine)
        vector_store = get_vector_store()
        
        if request.object_type == ObjectType.TABLE:
            # Discover table metadata
            columns = inspector.get_columns(request.object_name, schema=request.schema_name)
            pk_constraint = inspector.get_pk_constraint(request.object_name, schema=request.schema_name)
            fk_constraints = inspector.get_foreign_keys(request.object_name, schema=request.schema_name)
            
            # Build TableSchema object (legacy format)
            from app.models.schemas import TableSchema, ColumnInfo
            table_schema = TableSchema(
                schema_name=request.schema_name,
                table_name=request.object_name,
                table_type="table",
                columns=[ColumnInfo(name=c['name'], data_type=str(c['type'])) for c in columns]
            )
            
            # Build markdown description
            markdown = build_table_markdown_description(
                table_schema, pk_constraint, fk_constraints, "table"
            )
            
            # Create DataObject
            obj = DataObject(
                source_id=request.source_id,
                schema_name=request.schema_name,
                object_name=request.object_name,
                object_type=ObjectType.TABLE,
                description=markdown,
                columns=table_schema.columns
            )
            
            embedding_text = f"{obj.object_name} table"
            vector_store.insert_data_object_v2(obj, embedding_text)
        
        elif request.object_type == ObjectType.VIEW:
            # Similar to table
            columns = inspector.get_columns(request.object_name, schema=request.schema_name)
            from app.models.schemas import TableSchema, ColumnInfo
            
            table_schema = TableSchema(
                schema_name=request.schema_name,
                table_name=request.object_name,
                table_type="view",
                columns=[ColumnInfo(name=c['name'], data_type=str(c['type'])) for c in columns]
            )
            
            markdown = build_table_markdown_description(
                table_schema, None, [], "view"
            )
            
            obj = DataObject(
                source_id=request.source_id,
                schema_name=request.schema_name,
                object_name=request.object_name,
                object_type=ObjectType.VIEW,
                description=markdown,
                columns=table_schema.columns
            )
            
            embedding_text = f"{obj.object_name} view"
            vector_store.insert_data_object_v2(obj, embedding_text)
        
        elif request.object_type == ObjectType.STORED_PROCEDURE:
            # Discover stored procedure
            sps = discover_stored_procedures(engine, request.schema_name)
            sp = next((s for s in sps if s.object_name == request.object_name), None)
            
            if not sp:
                raise HTTPException(status_code=404, detail=f"Stored procedure {request.object_name} not found")
            
            sp.source_id = request.source_id
            markdown = build_sp_markdown_description(sp)
            sp.description = markdown
            
            embedding_text = f"{sp.object_name} stored procedure"
            vector_store.insert_data_object_v2(sp, embedding_text)
        
        elif request.object_type == ObjectType.FUNCTION:
            # Discover function
            funcs = discover_functions(engine, request.schema_name)
            func = next((f for f in funcs if f.object_name == request.object_name), None)
            
            if not func:
                raise HTTPException(status_code=404, detail=f"Function {request.object_name} not found")
            
            func.source_id = request.source_id
            markdown = build_function_markdown_description(func)
            func.description = markdown
            
            embedding_text = f"{func.object_name} function"
            vector_store.insert_data_object_v2(func, embedding_text)
        
        return {"status": "success", "message": f"Synced {request.object_name} from database"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync object: {str(e)}")


@router.delete("/object")
def delete_data_object(source_id: str, schema: str, object_name: str, current_user: User = Depends(get_current_active_admin)):
    """Delete a data object from vector store."""
    try:
        vector_store = get_vector_store()
        vector_store.delete_data_object_v2(source_id, schema, object_name)
        return {"status": "success", "message": f"Deleted {schema}.{object_name} from vector store"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/object/discover")
def discover_objects(request: DiscoverObjectsRequest, current_user: User = Depends(get_current_active_admin)):
    """
    Discover objects from database without adding to vector store.
    
    Returns list of discovered objects that can be selectively synced.
    """
    try:
        from app.core.database import get_database_engine
        from app.services.object_discovery_service import (
            discover_stored_procedures, discover_functions, discover_all_schemas
        )
        from sqlalchemy import inspect
        
        engine = get_database_engine(request.source_id)
        inspector = inspect(engine)
        
        discovered = []
        
        # Determine which schemas to search
        if request.schema_name:
            schemas = [request.schema_name]
        else:
            schemas = discover_all_schemas(engine)
        
        # Discover objects by type
        for schema in schemas:
            if ObjectType.TABLE in request.object_types:
                tables = inspector.get_table_names(schema=schema)
                for table in tables:
                    discovered.append(DataObject(
                        source_id=request.source_id,
                        schema_name=schema,
                        object_name=table,
                        object_type=ObjectType.TABLE,
                        description=f"Table: {table}",
                        columns=[]
                    ))
            
            if ObjectType.VIEW in request.object_types:
                views = inspector.get_view_names(schema=schema)
                for view in views:
                    discovered.append(DataObject(
                        source_id=request.source_id,
                        schema_name=schema,
                        object_name=view,
                        object_type=ObjectType.VIEW,
                        description=f"View: {view}",
                        columns=[]
                    ))
            
            if ObjectType.STORED_PROCEDURE in request.object_types:
                sps = discover_stored_procedures(engine, schema)
                discovered.extend(sps)
            
            if ObjectType.FUNCTION in request.object_types:
                funcs = discover_functions(engine, schema)
                discovered.extend(funcs)
        
        # Count by type
        by_type = {}
        for obj in discovered:
            obj_type = obj.object_type.value
            by_type[obj_type] = by_type.get(obj_type, 0) + 1
        
        return DiscoverObjectsResponse(
            discovered=discovered,
            total_count=len(discovered),
            by_type=by_type
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to discover objects: {str(e)}")

@router.post("/ingest-fewshots")
async def ingest_fewshots(file: UploadFile = File(...), mode: str = Form("append"), source_id: Optional[str] = Form(None), current_user: User = Depends(get_current_active_admin)):
    """
    Upload an Excel file to ingest few-shot examples.
    
    File format required:
    - Column 1: question (natural language question)
    - Column 2: sql_query (correct SQL query)
    """
    global _upload_progress
    
    try:
        if not source_id:
            raise HTTPException(status_code=400, detail="A data source must be selected before uploading. Please select a data source and try again.")
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="File must be Excel format (.xlsx or .xls)")
        
        contents = await file.read()
        
        # Initialize progress tracking
        _upload_progress = {"current": 0, "total": 0, "status": "processing"}
        
        # Give frontend time to establish SSE connection (200ms)
        await asyncio.sleep(0.2)
        
        # Define progress callback
        def progress_callback(current: int, total: int):
            global _upload_progress
            _upload_progress = {"current": current, "total": total, "status": "processing"}
        
        result = ingest_fewshots_from_excel(contents, mode, progress_callback, source_id=source_id)
        
        # Mark as complete
        _upload_progress = {"current": result.get("rows_processed", 0), "total": result.get("total_rows", 0), "status": "complete"}
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        _upload_progress = {"current": 0, "total": 0, "status": "error"}
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

# --- Few-Shot Management ---

@router.get("/fewshots", response_model=List[FewShotItem])
def get_fewshots(current_user: User = Depends(get_current_active_admin)):
    try:
        vector_store = get_vector_store()
        raw_items = vector_store.get_all_fewshots()
        # Clean up output
        results = []
        for r in raw_items:
            results.append(FewShotItem(
                id=str(r.get("id")),
                question=r.get("question"),
                sql_query=r.get("sql_query"),
                knowledge_type=r.get("knowledge_type", "sql_query"),  # Default to sql_query for backward compatibility
                verified=True
            ))
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/fewshots")
def add_fewshot(item: FewShotItem, current_user: User = Depends(get_current_active_admin)):
    try:
        vector_store = get_vector_store()
        vector_store.insert_fewshot_item(
            item.question, 
            item.sql_query, 
            item.knowledge_type if item.knowledge_type else "sql_query"
        )
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/fewshots/{item_id}")
def delete_fewshot(item_id: str, current_user: User = Depends(get_current_active_admin)):
    try:
        vector_store = get_vector_store()
        vector_store.delete_fewshot_item(int(item_id))
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fewshots/export")
def export_fewshots(current_user: User = Depends(get_current_active_admin)):
    """
    Export all knowledge base examples from the vector store to an Excel file.
    """
    from pandas import DataFrame
    
    try:
        vector_store = get_vector_store()
        fewshots = vector_store.get_all_fewshots()
        
        # Prepare data for export (exclude embeddings)
        export_data = []
        for item in fewshots:
            export_data.append({
                'question': item.get('question', ''),
                'sql_query': item.get('sql_query', ''),
                'knowledge_type': item.get('knowledge_type', 'sql_query')
            })
        
        df = DataFrame(export_data)
        
        # Create temp file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_path = os.path.join(tempfile.gettempdir(), f'knowledge_base_{timestamp}.xlsx')
        df.to_excel(temp_path, index=False)
        
        return FileResponse(
            temp_path,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename=f'knowledge_base_{timestamp}.xlsx'
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting knowledge base: {str(e)}")

# --- Value Index Management ---

@router.post("/ingest-values")
async def ingest_values(file: UploadFile = File(...), mode: str = Form("append"), source_id: Optional[str] = Form(None), current_user: User = Depends(get_current_active_admin)):
    """
    Upload an Excel or CSV file to ingest values into the value index.
    
    File format required:
    - Column 1: value (the actual database value)
    - Column 2: schema_name (e.g., 'dbo')
    - Column 3: table_name (e.g., 'Customers')
    - Column 4: column_name (e.g., 'Country')
    - Column 5: metadata (optional, JSON-formatted)
    """
    global _upload_progress
    
    try:
        if not source_id:
            raise HTTPException(status_code=400, detail="A data source must be selected before uploading. Please select a data source and try again.")
        
        if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            raise HTTPException(status_code=400, detail="File must be Excel (.xlsx/.xls) or CSV format")
        
        # Determine file type
        file_type = "csv" if file.filename.endswith('.csv') else "xlsx"
        
        contents = await file.read()
        
        # Initialize progress tracking
        _upload_progress = {"current": 0, "total": 0, "status": "processing"}
        
        # Give frontend time to establish SSE connection (200ms)
        await asyncio.sleep(0.2)
        
        # Define progress callback
        def progress_callback(current: int, total: int):
            global _upload_progress
            _upload_progress = {"current": current, "total": total, "status": "processing"}
        
        result = ingest_values_from_excel(contents, mode, file_type, progress_callback, source_id=source_id)
        
        # Mark as complete
        _upload_progress = {"current": result.get("rows_processed", 0), "total": result.get("total_rows", 0), "status": "complete"}
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        _upload_progress = {"current": 0, "total": 0, "status": "error"}
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@router.get("/ingest-progress")
async def get_upload_progress():
    """
    Get the current upload progress (SSE endpoint).
    """
    global _upload_progress
    
    async def progress_generator():
        # Send progress updates at regular intervals
        while True:
            current = _upload_progress.get("current", 0)
            total = _upload_progress.get("total", 0)
            status = _upload_progress.get("status", "idle")
            
            # Calculate percentage
            if total > 0:
                percentage = int((current / total) * 100)
            else:
                percentage = 0
            
            # Send progress as JSON event
            event_data = json.dumps({
                "current": current,
                "total": total,
                "percentage": percentage,
                "status": status
            })
            
            yield f"data: {event_data}\n\n"
            
            # Stop sending if upload is complete or has error
            if status in ["complete", "error"]:
                break
            
            # Wait before next update
            await asyncio.sleep(0.5)
    
    return StreamingResponse(
        progress_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/values/search", response_model=List[Dict])
def search_values(query: str, top_k: int = 50, current_user: User = Depends(get_current_active_admin)):
    """
    Search for values in the value index using plain text matching.
    
    Args:
        query: The search term to match against values (case-insensitive)
        top_k: Maximum number of results to return (default: 50)
    
    Returns:
        List of matching value items
    """
    try:
        vector_store = get_vector_store()
        results = vector_store.search_values(query, top_k)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/values", response_model=List[Dict])
def get_values(current_user: User = Depends(get_current_active_admin)):
    """
    Get all values currently in the value index.
    """
    try:
        values = get_all_values()
        return values
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/values/{item_id}")
def delete_value(item_id: int, current_user: User = Depends(get_current_active_admin)):
    """
    Delete a specific value item from the index.
    """
    try:
        success = delete_value_item(item_id)
        if success:
            return {"status": "success", "message": f"Deleted value {item_id}"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete value")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/values/clear")
def clear_values(current_user: User = Depends(get_current_active_admin)):
    """
    Clear all values from the value index.
    """
    try:
        success = clear_all_values()
        if success:
            return {"status": "success", "message": "Cleared all values from index"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear values")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/values/template")
def get_excel_template(current_user: User = Depends(get_current_active_admin)):
    """
    Download a template Excel file for value ingestion.
    """
    from pandas import DataFrame
    
    # Create template DataFrame
    template_data = {
        'value': ['example_value_1', 'example_value_2', 'North America'],
        'schema_name': ['dbo', 'dbo', 'dbo'],
        'table_name': ['Customers', 'Products', 'Territories'],
        'column_name': ['Country', 'Category', 'RegionDescription'],
        'metadata': ['{}', '{}', '{}']
    }
    
    df = DataFrame(template_data)
    
    # Save to temporary file
    temp_path = os.path.join(tempfile.gettempdir(), 'value_index_template.xlsx')
    df.to_excel(temp_path, index=False)
    
    return FileResponse(
        temp_path,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        filename='value_index_template.xlsx'
    )

@router.get("/values/export")
def export_values(current_user: User = Depends(get_current_active_admin)):
    """
    Export all values from the value index to an Excel file.
    """
    from pandas import DataFrame
    
    try:
        values = get_all_values()
        
        # Prepare data for export (exclude embeddings)
        export_data = []
        for item in values:
            export_data.append({
                'value': item.get('value', ''),
                'schema_name': item.get('schema_name', ''),
                'table_name': item.get('table_name', ''),
                'column_name': item.get('column_name', '')
            })
        
        df = DataFrame(export_data)
        
        # Create temp file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_path = os.path.join(tempfile.gettempdir(), f'value_index_{timestamp}.xlsx')
        df.to_excel(temp_path, index=False)
        
        return FileResponse(
            temp_path,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename=f'value_index_{timestamp}.xlsx'
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting values: {str(e)}")

@router.get("/vector-store/backup")
def backup_vector_store(current_user: User = Depends(get_current_active_admin)):
    """
    Backup all vector store data (Schemas, FewShots, Values) to a JSON file.
    """
    try:
        vector_store = get_vector_store()
        data = vector_store.export_all_data()
        
        # Save to temp file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'vector_store_backup_{timestamp}.json'
        temp_path = os.path.join(tempfile.gettempdir(), filename)
        
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        return FileResponse(
            temp_path,
            media_type='application/json',
            filename=filename
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating backup: {str(e)}")


# --- Skills Management ---

@router.get("/skills/data-sources")
def get_data_sources(current_user: User = Depends(get_current_active_admin)):
    """Get all data sources from skills index"""
    try:
        skills_service = get_skills_service()
        # Clear cache to get fresh data
        skills_service._data_sources_cache = None
        data_sources = skills_service.load_data_sources_index()
        return [ds.model_dump() for ds in data_sources if ds is not None]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/data-sources")
def create_data_source(data: Dict, current_user: User = Depends(get_current_active_admin)):
    """Create a new data source"""
    try:
        from app.services.skills_admin_service import create_data_source as create_ds
        result = create_ds(data)
        return {"status": "success", "message": f"Created data source: {data.get('name')}", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/skills/data-sources/{data_source_name}")
def update_data_source(data_source_name: str, data: Dict, current_user: User = Depends(get_current_active_admin)):
    """Update an existing data source"""
    try:
        from app.services.skills_admin_service import update_data_source as update_ds
        result = update_ds(data_source_name, data)
        return {"status": "success", "message": f"Updated data source: {data_source_name}", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/skills/data-sources/{data_source_name}")
def delete_data_source(data_source_name: str, current_user: User = Depends(get_current_active_admin)):
    """Delete a data source and all its contents"""
    try:
        from app.services.skills_admin_service import delete_data_source as delete_ds
        delete_ds(data_source_name)
        return {"status": "success", "message": f"Deleted data source: {data_source_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/data-groups")
def get_data_groups(data_source: Optional[str] = None, current_user: User = Depends(get_current_active_admin)):
    """Get all data groups, optionally filtered by data source"""
    try:
        skills_service = get_skills_service()
        # Clear cache to get fresh data
        skills_service._data_groups_cache = None
        all_groups = skills_service.load_all_data_groups()
        
        groups = list(all_groups.values())
        if data_source:
            groups = [g for g in groups if g.data_source == data_source]
        
        return [g.model_dump() for g in groups if g is not None]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/data-groups")
def create_data_group(data: Dict, current_user: User = Depends(get_current_active_admin)):
    """Create a new data group"""
    try:
        from app.services.skills_admin_service import create_data_group as create_dg
        result = create_dg(data)
        return {"status": "success", "message": f"Created data group: {data.get('name')}", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/skills/data-groups")
def update_data_group(data: Dict, current_user: User = Depends(get_current_active_admin)):
    """Update an existing data group (requires file_path in data)"""
    try:
        from app.services.skills_admin_service import update_data_group as update_dg
        result = update_dg(data)
        return {"status": "success", "message": f"Updated data group: {data.get('name')}", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/skills/data-groups")
def delete_data_group(file_path: str, current_user: User = Depends(get_current_active_admin)):
    """Delete a data group file"""
    try:
        from app.services.skills_admin_service import delete_data_group as delete_dg
        delete_dg(file_path)
        return {"status": "success", "message": "Deleted data group"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/tables")
def get_tables(data_source: Optional[str] = None, data_group: Optional[str] = None, current_user: User = Depends(get_current_active_admin)):
    """Get table schemas, optionally filtered by data source or data group"""
    try:
        skills_service = get_skills_service()
        all_groups = skills_service.load_all_data_groups()
        
        # Filter groups
        groups = list(all_groups.values())
        if data_source:
            groups = [g for g in groups if g.data_source == data_source]
        if data_group:
            groups = [g for g in groups if g.name == data_group]
        
        # Collect all table paths
        table_paths = []
        for g in groups:
            table_paths.extend(g.tables)
        
        # Load table schemas
        tables = skills_service.load_table_schemas(table_paths)
        return [t.model_dump() for t in tables if t is not None]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/tables/by-path")
def get_table_by_path(file_path: str, current_user: User = Depends(get_current_active_admin)):
    """Get a specific table schema by file path"""
    try:
        skills_service = get_skills_service()
        tables = skills_service.load_table_schemas([file_path])
        if not tables:
            raise HTTPException(status_code=404, detail="Table not found")
        return tables[0].model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/tables")
def create_table(data: Dict, current_user: User = Depends(get_current_active_admin)):
    """Create a new table schema (data object)"""
    try:
        from app.services.skills_admin_service import create_table_schema as create_ts
        result = create_ts(data)
        return {"status": "success", "message": f"Created table: {data.get('schema_name')}.{data.get('table_name')}", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/skills/tables")
def update_table(data: Dict, current_user: User = Depends(get_current_active_admin)):
    """Update an existing table schema (requires file_path in data)"""
    try:
        from app.services.skills_admin_service import update_table_schema as update_ts
        result = update_ts(data)
        return {"status": "success", "message": f"Updated table: {data.get('table_name')}", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/skills/tables")
def delete_table(file_path: str, current_user: User = Depends(get_current_active_admin)):
    """Delete a table schema file"""
    try:
        from app.services.skills_admin_service import delete_table_schema as delete_ts
        delete_ts(file_path)
        return {"status": "success", "message": "Deleted table schema"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/raw-markdown")
def get_raw_markdown(file_path: str, current_user: User = Depends(get_current_active_admin)):
    """Get raw markdown content of a skill file"""
    try:
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        content = path.read_text(encoding='utf-8')
        return {"content": content, "file_path": file_path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/skills/raw-markdown")
def save_raw_markdown(data: Dict, current_user: User = Depends(get_current_active_admin)):
    """Save raw markdown content to a skill file"""
    try:
        from pathlib import Path
        file_path = data.get('file_path')
        content = data.get('content')
        
        if not file_path or content is None:
            raise HTTPException(status_code=400, detail="file_path and content are required")
        
        path = Path(file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        path.write_text(content, encoding='utf-8')
        
        # Clear skills service cache to reload data
        skills_service = get_skills_service()
        skills_service._data_sources_cache = None
        skills_service._data_groups_cache = None
        
        return {"status": "success", "message": "Markdown file saved", "file_path": file_path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/folder-tree")
def get_folder_tree(current_user: User = Depends(get_current_active_admin)):
    """Get the actual folder hierarchy from skills/data-sources directory"""
    try:
        from pathlib import Path
        import os
        
        def build_tree(path: Path, relative_to: Path) -> Dict:
            """Recursively build folder tree"""
            item = {
                "name": path.name,
                "path": str(path),
                "relative_path": str(path.relative_to(relative_to)),
                "is_file": path.is_file(),
                "type": "file" if path.is_file() else "folder"
            }
            
            if path.is_file():
                # Add file metadata
                item["extension"] = path.suffix
                item["is_markdown"] = path.suffix == ".md"
            else:
                # Add folder children
                children = []
                try:
                    for child in sorted(path.iterdir()):
                        # Skip hidden files/folders
                        if not child.name.startswith('.'):
                            children.append(build_tree(child, relative_to))
                except PermissionError:
                    pass
                item["children"] = children
            
            return item
        
        base_path = Path("skills/data-sources")
        if not base_path.exists():
            return {"error": "skills/data-sources directory not found"}
        
        tree = build_tree(base_path, base_path.parent)
        return tree
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enhance-schema", response_model=EnhanceSchemaResponse)
def enhance_schema_with_ai(
    request: EnhanceSchemaRequest,
    current_user: User = Depends(get_current_active_admin)
):
    """
    Enhance table and column descriptions using AI.
    Combines markdown parsing, database schema queries, and LLM generation.
    """
    try:
        from app.services.schema_enhancement_service import SchemaEnhancementService
        
        service = SchemaEnhancementService()
        enhanced_md = service.enhance_schema(
            file_path=request.file_path,
            current_content=request.current_content,
            user_context=request.user_context
        )
        
        return EnhanceSchemaResponse(enhanced_markdown=enhanced_md)
    except ValueError as e:
        # Handle validation errors from service
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error enhancing schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =======================
# Index-Based Schema Search Endpoints
# =======================

@router.get("/skills/search")
def search_schemas(
    query: str,
    data_source: Optional[str] = None,
    object_type: Optional[str] = None,
    top_k: int = 10,
    current_user: User = Depends(get_current_active_admin)
):
    """
    Search for data objects using keyword-based index search
    
    Args:
        query: Search keywords
        data_source: Optional filter by data source name
        object_type: Optional filter by object type (Table/View)
        top_k: Maximum number of results (default: 10)
    """
    try:
        skills_service = get_skills_service()
        results = skills_service.search_objects_by_keyword(
            query=query,
            data_source=data_source,
            object_type=object_type,
            top_k=top_k
        )
        return {
            "query": query,
            "total_results": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/objects")
def list_objects(
    data_source: Optional[str] = None,
    schema_name: Optional[str] = None,
    current_user: User = Depends(get_current_active_admin)
):
    """
    List all available data objects from index files
    
    Args:
        data_source: Optional filter by data source name
        schema_name: Optional filter by schema name
    """
    try:
        skills_service = get_skills_service()
        objects = skills_service.list_all_objects(
            data_source=data_source,
            schema_name=schema_name
        )
        return {
            "total_objects": len(objects),
            "objects": objects
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/objects/by-name")
def get_object_by_name(
    object_name: str,
    schema_name: str = "dbo",
    data_source: Optional[str] = None,
    current_user: User = Depends(get_current_active_admin)
):
    """
    Get a specific data object by name using index files
    
    Args:
        object_name: Name of the table/view
        schema_name: Schema name (default: dbo)
        data_source: Optional data source name
    """
    try:
        skills_service = get_skills_service()
        obj = skills_service.get_object_by_name(
            object_name=object_name,
            schema_name=schema_name,
            data_source=data_source
        )
        if not obj:
            raise HTTPException(status_code=404, detail=f"Object '{schema_name}.{object_name}' not found")
        return obj
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills/statistics")
def get_schema_statistics(
    data_source: Optional[str] = None,
    current_user: User = Depends(get_current_active_admin)
):
    """
    Get statistics about available schemas using index files
    
    Args:
        data_source: Optional filter by data source name
    """
    try:
        skills_service = get_skills_service()
        stats = skills_service.get_schema_statistics(data_source=data_source)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/skills/regenerate-indices")
def regenerate_schema_indices(current_user: User = Depends(get_current_active_admin)):
    """
    Regenerate all schema index files (.schema-index.json and .object-index.json)
    """
    try:
        import subprocess
        import sys
        
        # Run the generate_schema_indices.py script
        script_path = "scripts/generate_schema_indices.py"
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # Clear cache to force reload
            skills_service = get_skills_service()
            skills_service.clear_cache()
            
            return {
                "status": "success",
                "message": "Schema indices regenerated successfully",
                "output": result.stdout
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to regenerate indices: {result.stderr}"
            )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Index regeneration timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


