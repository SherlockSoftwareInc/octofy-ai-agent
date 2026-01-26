from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from fastapi.responses import StreamingResponse, FileResponse
from typing import List, Dict
from app.models.schemas import AdminSchemaStatus, FewShotItem, ValueIndexItem, BatchSyncRequest, BatchSyncResponse
from app.services.admin_service import (
    get_schema_status, sync_specific_table, sync_all_schemas, batch_sync_tables,
    ingest_values_from_excel, get_all_values, delete_value_item, clear_all_values,
    ingest_schemas_from_excel, ingest_fewshots_from_excel
)
from app.services.vector_store import get_vector_store
from app.core.auth import verify_api_key
import json
import asyncio
import os
import tempfile
from datetime import datetime

router = APIRouter()

# Global state for tracking upload progress
_upload_progress = {"current": 0, "total": 0, "status": "idle"}

# --- Schema Management ---

@router.get("/schema/status", response_model=List[AdminSchemaStatus])
def get_schemas_status(api_key: str = Depends(verify_api_key)):
    try:
        return get_schema_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/schema/sync")
def sync_table(schema: str, table: str, api_key: str = Depends(verify_api_key)):
    try:
        success = sync_specific_table(schema, table)
        return {"status": "success", "message": f"Synced {schema}.{table}"}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/schema/sync-full")
def sync_all(api_key: str = Depends(verify_api_key)):
    try:
        sync_all_schemas()
        return {"status": "success", "message": "Successfully synced all schemas and rebuilt vector index"}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/schema/batch-sync", response_model=BatchSyncResponse)
def batch_sync(request: BatchSyncRequest, api_key: str = Depends(verify_api_key)):
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
        
        result = batch_sync_tables(request.table_names)
        return BatchSyncResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/schema/description")
def update_schema_description(schema: str, table: str, description: str, api_key: str = Depends(verify_api_key)):
    try:
        vector_store = get_vector_store()
        vector_store.update_schema_description(schema, table, description)
        return {"status": "success", "message": f"Updated description for {schema}.{table}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/schema")
def delete_schema(schema: str, table: str, api_key: str = Depends(verify_api_key)):
    try:
        vector_store = get_vector_store()
        vector_store.delete_schema(schema, table)
        return {"status": "success", "message": f"Deleted {schema}.{table} from vector store"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schema/export")
def export_schemas(api_key: str = Depends(verify_api_key)):
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
async def ingest_schemas(file: UploadFile = File(...), mode: str = "append", api_key: str = Depends(verify_api_key)):
    """
    Upload an Excel file to ingest schema/table metadata.
    
    File format required:
    - Column 1: schema_name (e.g., 'dbo')
    - Column 2: table_name (e.g., 'Customers')
    - Column 3: description (table description)
    """
    global _upload_progress
    
    try:
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
        
        result = ingest_schemas_from_excel(contents, mode, progress_callback)
        
        # Mark as complete
        _upload_progress = {"current": result.get("rows_processed", 0), "total": result.get("total_rows", 0), "status": "complete"}
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        _upload_progress = {"current": 0, "total": 0, "status": "error"}
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@router.get("/schema/template")
def get_schema_template(api_key: str = Depends(verify_api_key)):
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
def clear_all_schemas_endpoint(api_key: str = Depends(verify_api_key)):
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

@router.post("/ingest-fewshots")
async def ingest_fewshots(file: UploadFile = File(...), mode: str = "append", api_key: str = Depends(verify_api_key)):
    """
    Upload an Excel file to ingest few-shot examples.
    
    File format required:
    - Column 1: question (natural language question)
    - Column 2: sql_query (correct SQL query)
    """
    global _upload_progress
    
    try:
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
        
        result = ingest_fewshots_from_excel(contents, mode, progress_callback)
        
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
def get_fewshots(api_key: str = Depends(verify_api_key)):
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
def add_fewshot(item: FewShotItem, api_key: str = Depends(verify_api_key)):
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
def delete_fewshot(item_id: str, api_key: str = Depends(verify_api_key)):
    try:
        vector_store = get_vector_store()
        vector_store.delete_fewshot_item(int(item_id))
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/fewshots/export")
def export_fewshots(api_key: str = Depends(verify_api_key)):
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
async def ingest_values(file: UploadFile = File(...), mode: str = "append", api_key: str = Depends(verify_api_key)):
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
        
        result = ingest_values_from_excel(contents, mode, file_type, progress_callback)
        
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
def search_values(query: str, top_k: int = 50, api_key: str = Depends(verify_api_key)):
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
def get_values(api_key: str = Depends(verify_api_key)):
    """
    Get all values currently in the value index.
    """
    try:
        values = get_all_values()
        return values
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/values/{item_id}")
def delete_value(item_id: int, api_key: str = Depends(verify_api_key)):
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
def clear_values(api_key: str = Depends(verify_api_key)):
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
def get_excel_template(api_key: str = Depends(verify_api_key)):
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
def export_values(api_key: str = Depends(verify_api_key)):
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
def backup_vector_store(api_key: str = Depends(verify_api_key)):
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

