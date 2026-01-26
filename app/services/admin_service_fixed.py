from app.core.database import get_db_engine
from typing import List, Dict, Any
from app.models.schemas import TableSchema, AdminSchemaStatus, ColumnInfo, ValueIndexItem
from app.services.vector_store import get_vector_store
from sqlalchemy import inspect
import json
import io
from pandas import read_excel, read_csv, DataFrame

def get_schema_status() -> List[AdminSchemaStatus]:
    vector_store = get_vector_store()
    # 1. Get real DB tables (Try-Catch for DB Connection issues)
    engine = get_db_engine()
    db_tables = []
    inspector = None
    db_connection_error = False
    
    try:
        inspector = inspect(engine)
        for schema in inspector.get_schema_names():
            if schema in ['information_schema', 'sys', 'guest', 'sysadmin']: continue
            for table in inspector.get_table_names(schema=schema):
                db_tables.append((schema, table))
    except Exception as e:
        print(f"Warning: Failed to inspect database: {e}")
        db_connection_error = True

    # 2. Get indexed tables from Milvus
    indexed_schemas = vector_store.get_all_schemas()
    indexed_map = {f"{s.schema_name}.{s.table_name}": s for s in indexed_schemas}
    
    # 3. Merge
    status_list = []
    processed_keys = set()
    
    # Process DB tables if available
    for schema, table in db_tables:
        key = f"{schema}.{table}"
        processed_keys.add(key)
        
        # Get column count (lightweight)
        col_count = 0
        try:
             cols = inspector.get_columns(table, schema=schema)
             col_count = len(cols)
        except: pass
        
        is_indexed = key in indexed_map
        indexed_obj = indexed_map.get(key)
        desc = indexed_obj.description if is_indexed else None
        table_type = indexed_obj.table_type if is_indexed and hasattr(indexed_obj, 'table_type') else 'table'
        
        status_list.append(AdminSchemaStatus(
            schema_name=schema,
            table_name=table,
            table_type=table_type,
            is_indexed=is_indexed,
            description=desc,
            column_count=col_count,
            last_updated="Live"
        ))
        
    # Append indexed tables that weren't found in DB (Orphaned or DB is down)
    for key, schema_obj in indexed_map.items():
        if key not in processed_keys:
             status_list.append(AdminSchemaStatus(
                schema_name=schema_obj.schema_name,
                table_name=schema_obj.table_name,
                table_type=getattr(schema_obj, 'table_type', 'table') or 'table',
                is_indexed=True,
                description=schema_obj.description,
                column_count=len(schema_obj.columns),
                last_updated="Indexed (DB Error)" if db_connection_error else "Orphaned"
            ))

    return status_list

def sync_specific_table(schema_name: str, table_name: str):
    # 1. Inspect DB
    engine = get_db_engine()
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name, schema=schema_name)
    
    # Detect if this is a table or view
    table_type = 'table'
    tables = inspector.get_table_names(schema=schema_name)
    views = inspector.get_view_names(schema=schema_name)
    if table_name in views:
        table_type = 'view'
    elif table_name not in tables:
        # Object not found in either - default to table
        table_type = 'table'
    
    col_list = []
    col_text_parts = []
    for col in columns:
        col_info = ColumnInfo(
            name=col['name'],
            data_type=str(col['type']),
            description=col.get('comment', '')
        )
        col_list.append(col_info)
        col_text_parts.append(f"{col['name']} ({col['type']})")
    
    # 2. Generate Description (using existing stub or later LLM)
    # For now, we construct a default one if not providing override
    full_text = f"{table_type.capitalize()} {schema_name}.{table_name}. Columns: {', '.join(col_text_parts)}."
    
    schema_obj = TableSchema(
        schema_name=schema_name,
        table_name=table_name,
        table_type=table_type,
        description=full_text,
        columns=col_list
    )
    
    # 3. Update Vector Store
    vector_store = get_vector_store()
    vector_store.insert_schema_embedding(schema_obj, full_text)
    return True

def sync_all_schemas():
    """
    Sync all schemas from the database and rebuild the vector index.
    This is used when the vector store is empty or needs to be reset.
    """
    from app.services.ingest_service import create_milvus_collections, ingest_metadata
    
    try:
        # Recreate collections and ingest all metadata
        create_milvus_collections()
        ingest_metadata()
        return True
    except Exception as e:
        print(f"Error syncing all schemas: {e}")
        raise

# --- Value Index Management ---

def ingest_values_from_excel(file_content: bytes, mode: str = "append", file_type: str = "xlsx") -> Dict[str, Any]:
    """
    Parse Excel or CSV file and ingest values into the value index.
    
    File format required:
    - Column 1: value (the actual database value)
    - Column 2: schema_name (e.g., 'dbo')
    - Column 3: table_name (e.g., 'Customers')
    - Column 4: column_name (e.g., 'Country')
    - Column 5: metadata (optional, JSON-formatted)
    
    Args:
        file_content: Binary file content
        mode: "append" to add to existing values, "replace" to clear and reload
        file_type: "csv" or "xlsx" to indicate file format
    
    Returns:
        Dictionary with ingestion results
    """
    vector_store = get_vector_store()
    try:
        # Read file based on type
        if file_type.lower() == "csv":
            df = read_csv(io.BytesIO(file_content))
        else:
            df = read_excel(io.BytesIO(file_content))
        
        # Normalize column names: strip whitespace and lowercase for comparison
        df.columns = df.columns.str.strip().str.lower()
        
        # Validate columns (case-insensitive)
        required_cols = ['value', 'schema_name', 'table_name', 'column_name']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            # Check if we have the required columns but with different names
            available_cols = df.columns.tolist()
            return {
                "status": "error",
                "message": f"File must contain columns: {', '.join(required_cols)}. Found: {', '.join(available_cols)}",
                "rows_processed": 0
            }
        
        # Clean and deduplicate
        df = df[required_cols + [col for col in df.columns if col not in required_cols]]
        df['value'] = df['value'].astype(str).str.strip()
        df = df.drop_duplicates(subset=['value', 'schema_name', 'table_name', 'column_name'])
        df = df[df['value'].notna() & (df['value'] != '')]
        
        if df.empty:
            return {
                "status": "error",
                "message": "No valid values found in file",
                "rows_processed": 0
            }
        
        # If replacing, clear existing values first
        if mode == "replace":
            vector_store.clear_values_collection()
        
        # Ingest each row
        success_count = 0
        for idx, row in df.iterrows():
            try:
                # Handle metadata field if present
                metadata = {}
                if 'metadata' in df.columns:
                    try:
                        meta_val = row.get('metadata', '{}')
                        if isinstance(meta_val, str) and meta_val:
                            metadata = json.loads(meta_val)
                    except:
                        metadata = {}
                
                vector_store.insert_value_item(
                    value=str(row['value']),
                    schema_name=str(row['schema_name']),
                    table_name=str(row['table_name']),
                    column_name=str(row['column_name']),
                    metadata=metadata
                )
                success_count += 1
            except Exception as e:
                print(f"Failed to ingest row {idx}: {e}")
                continue
        
        return {
            "status": "success",
            "message": f"Successfully ingested {success_count} values",
            "rows_processed": success_count,
            "total_rows": len(df)
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error processing file: {str(e)}",
            "rows_processed": 0
        }

def get_all_values() -> List[Dict[str, Any]]:
    """
    Retrieve all values from the value index.
    """
    try:
        vector_store = get_vector_store()
        return vector_store.get_all_values()
    except Exception as e:
        print(f"Error retrieving values: {e}")
        return []

def delete_value_item(value_id: int) -> bool:
    """
    Delete a single value item from the index.
    """
    try:
        vector_store = get_vector_store()
        vector_store.delete_value_item(value_id)
        return True
    except Exception as e:
        print(f"Error deleting value: {e}")
        return False

def clear_all_values() -> bool:
    """
    Clear all values from the index.
    """
    try:
        vector_store = get_vector_store()
        vector_store.clear_values_collection()
        return True
    except Exception as e:
        print(f"Error clearing values: {e}")
        return False
