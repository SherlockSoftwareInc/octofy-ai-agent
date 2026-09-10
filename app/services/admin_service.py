from app.core.database import get_db_engine, get_database_engine
from typing import List, Dict, Any, Optional
from app.models.schemas import TableSchema, AdminSchemaStatus, ColumnInfo, ValueIndexItem
from app.services.vector_store import get_vector_store
from app.services.relationship_graph import invalidate_relationship_graph
from sqlalchemy import inspect, text
import json
import io
from pandas import read_excel, read_csv, DataFrame

def clean_column_type(col_type: Any) -> str:
    """
    Clean column data type by removing COLLATE clause.
    
    Example:
        'NVARCHAR(40) COLLATE "SQL_Latin1_General_CP1_CI_AS"' -> 'NVARCHAR(40)'
    
    Args:
        col_type: SQLAlchemy column type object or string
    
    Returns:
        Cleaned data type string without COLLATE clause
    """
    type_str = str(col_type)
    
    # Remove COLLATE clause if present (case-insensitive)
    if ' COLLATE ' in type_str.upper():
        # Find the position of COLLATE (case-insensitive)
        collate_idx = type_str.upper().find(' COLLATE ')
        if collate_idx != -1:
            type_str = type_str[:collate_idx].strip()
    
    return type_str


def get_foreign_key_map(inspector, table_name: str, schema_name: str) -> Dict[str, str]:
    """
    Get foreign key references for a table.
    
    Returns:
        Dict mapping column_name -> "[referred_schema].[referred_table].[referred_column]"
    """
    fk_map = {}
    try:
        fk_constraints = inspector.get_foreign_keys(table_name, schema=schema_name)
        for fk in fk_constraints:
            constrained_cols = fk.get('constrained_columns', [])
            referred_schema = fk.get('referred_schema') or schema_name
            referred_table = fk.get('referred_table', '')
            referred_cols = fk.get('referred_columns', [])
            
            # Map each constrained column to its reference
            for i, col in enumerate(constrained_cols):
                if i < len(referred_cols):
                    fk_map[col] = f"[{referred_schema}].[{referred_table}].[{referred_cols[i]}]"
    except Exception as e:
        print(f"Warning: Could not retrieve foreign keys for {schema_name}.{table_name}: {e}")
    
    return fk_map


def get_table_description(engine, table_name: str, schema_name: str, table_type: str = "table") -> str:
    """
    Get table/view description from SQL Server extended properties (MS_Description).
    
    Returns:
        The description string, or empty string if not found.
    """
    obj_type = "V" if (table_type or "").lower() == "view" else "U"
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT CAST(ep.value AS NVARCHAR(MAX)) as description
                FROM sys.extended_properties ep
                INNER JOIN sys.objects o ON ep.major_id = o.object_id
                INNER JOIN sys.schemas s ON o.schema_id = s.schema_id
                WHERE ep.minor_id = 0
                  AND ep.name = 'MS_Description'
                  AND s.name = :schema_name
                  AND o.name = :table_name
                  AND o.type = :obj_type
            """), {"schema_name": schema_name, "table_name": table_name, "obj_type": obj_type})
            row = result.fetchone()
            if row and row[0]:
                return str(row[0]).strip()
    except Exception as e:
        print(f"Warning: Could not retrieve {table_type} description for {schema_name}.{table_name}: {e}")
    
    return ""


def build_table_markdown_description(
    schema_name: str,
    table_name: str,
    table_description: str,
    columns: List[Dict[str, Any]],
    fk_map: Dict[str, str],
    table_type: str = "table"
) -> str:
    """
    Build a rich Markdown description for a table or view.
    
    Format:
    # **Table:** `[schema].[table]`  (or **View:** for views)
    > description
    ---
    ### **Columns:**
    | Ord | Name | Description |
    ...
    ---
    """
    # Header - use capitalized table_type (Table or View)
    type_label = table_type.capitalize() if table_type else "Table"
    md = f"# **{type_label}:** `[{schema_name}].[{table_name}]`\n"
    md += f"> {table_description}\n"
    md += "---\n"
    md += "### **Columns:**\n"
    md += "| Ord | Name | Description |\n"
    md += "|:---:|:---:|:---|\n"
    
    # Column rows
    for idx, col in enumerate(columns, start=1):
        col_name = col.get('name', '')
        col_desc = col.get('description', '') or col.get('comment', '') or ''
        
        # If column has FK reference, append it (but only if not already present)
        if col_name in fk_map and 'Reference:' not in col_desc:
            if col_desc:
                # Ensure col_desc ends with comma before appending Reference
                col_desc = col_desc.rstrip()
                if not col_desc.endswith('.'):
                    col_desc = f"{col_desc}."
                col_desc = f"{col_desc} Reference: {fk_map[col_name]}"
            else:
                col_desc = f"Reference: {fk_map[col_name]}"
        
        # If no description at all, leave empty
        if not col_desc:
            col_desc = ""
        
        md += f"| {idx} | `{col_name}` | {col_desc} |\n"
    
    md += "---\n"
    return md

def _object_type_label(raw: Any) -> str:
    value = str(raw or "table").strip().lower().replace(" ", "_")
    aliases = {
        "storedprocedure": "stored_procedure",
        "fn": "function",
        "func": "function",
    }
    return aliases.get(value, value or "table")


def schema_rows_to_admin_status(rows: List[Dict[str, Any]], source_id: Optional[str] = None) -> List[AdminSchemaStatus]:
    """Turn Milvus `schemas` rows (parents + columns) into the admin object list."""
    parents: Dict[tuple, Dict[str, Any]] = {}
    col_counts: Dict[tuple, int] = {}
    for row in rows or []:
        schema_name = (row.get("schema_name") or "dbo").strip()
        object_name = (row.get("object_name") or row.get("table_name") or "").strip()
        if not object_name:
            continue
        key = (schema_name, object_name)
        entity = str(row.get("entity_type") or "").strip().lower()
        if entity == "column":
            col_counts[key] = col_counts.get(key, 0) + 1
            continue
        parents[key] = row
    items: List[AdminSchemaStatus] = []
    for (schema_name, object_name), row in sorted(parents.items(), key=lambda item: (item[0][0].lower(), item[0][1].lower())):
        sid = row.get("data_source_id") or row.get("source_id") or source_id
        otype = _object_type_label(row.get("object_type") or row.get("table_type") or "table")
        items.append(AdminSchemaStatus(
            schema_name=schema_name,
            table_name=object_name,
            object_name=object_name,
            object_type=otype,
            table_type=otype,
            entity_type=row.get("entity_type") or "Table",
            is_indexed=True,
            description=row.get("description"),
            column_count=col_counts.get((schema_name, object_name), 0),
            source_id=sid,
        ))
    return items


def _collect_indexed_schemas(source_id: Optional[str] = None) -> List[AdminSchemaStatus]:
    """List parent objects from the Milvus `schemas` collection."""
    from app.services.stores.provider_factory import get_vector_provider

    provider = get_vector_provider()
    if source_id:
        rows = provider.fetch_all("schemas", source_id)
        return schema_rows_to_admin_status(rows, source_id)

    if hasattr(provider, "fetch_all_rows"):
        rows = provider.fetch_all_rows("schemas")
    else:
        rows = []
    if source_id:
        wanted = source_id.lower()
        rows = [row for row in rows if str(row.get("data_source_id") or "").lower() == wanted]
    return schema_rows_to_admin_status(rows, source_id)


def get_schema_status(include_database_inspection: bool = False, source_id: Optional[str] = None) -> List[AdminSchemaStatus]:
    indexed_schemas = _collect_indexed_schemas(source_id)
    
    # Skip database inspection if not requested (performance optimization)
    if not include_database_inspection:
        return indexed_schemas
    
    # 2. Get real DB tables and views (Try-Catch for DB Connection issues)
    # Build a set of what we need to check instead of getting ALL tables
    engine = get_db_engine()
    db_objects_set = set()  # Set of "schema.table" strings
    db_connection_error = False
    
    try:
        inspector = inspect(engine)
        for schema in inspector.get_schema_names():
            if schema in ['information_schema', 'sys', 'guest', 'sysadmin']: 
                continue
            # Get tables
            for table in inspector.get_table_names(schema=schema):
                db_objects_set.add(f"{schema}.{table}")
            # Get views  
            for view in inspector.get_view_names(schema=schema):
                db_objects_set.add(f"{schema}.{view}")
    except Exception as e:
        print(f"Warning: Failed to inspect database: {e}")
        db_connection_error = True
    
    # 3. Build result list (fast - no DB queries per item)
    status_list = []
    
    # Iterate through ALL indexed schemas
    for schema_obj in indexed_schemas:
        key = f"{schema_obj.schema_name}.{schema_obj.table_name}"
        is_live = key in db_objects_set
        
        # Determine status
        status = "Live" if is_live else ("Indexed (DB Error)" if db_connection_error else "Orphaned")
        schema_obj.last_updated = status
        status_list.append(schema_obj)
    
    return status_list

def sync_specific_table(schema_name: str, table_name: str, custom_description: Optional[str] = None, source_id: Optional[str] = None):
    """
    Sync a specific table or view from the database to the vector store.
    
    Args:
        schema_name: Database schema name (e.g., 'dbo')
        table_name: Table or view name
        custom_description: Optional custom table description. If not provided,
                           attempts to extract from database, then falls back to default.
        source_id: Optional data source ID for database connection
    """
    vector_store = get_vector_store()
    # 1. Inspect DB
    engine = get_database_engine(source_id) if source_id else get_db_engine()
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
    
    # 2. Get foreign key mappings (only for tables, views don't have FKs)
    fk_map = get_foreign_key_map(inspector, table_name, schema_name) if table_type == 'table' else {}
    
    # 3. Build column list with descriptions
    col_list = []
    columns_for_markdown = []
    for col in columns:
        col_desc = col.get('comment', '')
        col_info = ColumnInfo(
            name=col['name'],
            data_type=clean_column_type(col['type']),
            description=col_desc
        )
        col_list.append(col_info)
        columns_for_markdown.append({
            'name': col['name'],
            'data_type': clean_column_type(col['type']),
            'description': col_desc,
            'comment': col_desc
        })
    
    # 4. Get table description from database extended properties
    db_table_description = get_table_description(engine, table_name, schema_name, table_type)
    
    # 5. Generate table description for embedding
    # Priority: custom_description > db_table_description > default
    if custom_description:
        table_description = custom_description
    elif db_table_description:
        table_description = db_table_description
    else:
        table_description = f"This {table_type} stores {table_name} data."
    
    # 6. Build embedding text: [table_name] + [table_description]
    # Simple and semantic - no column counts
    embedding_text = f"{table_name} {table_description}"
    
    # 6. Build rich Markdown description for storage
    markdown_description = build_table_markdown_description(
        schema_name=schema_name,
        table_name=table_name,
        table_description=table_description,
        columns=columns_for_markdown,
        fk_map=fk_map,
        table_type=table_type
    )
    
    schema_obj = TableSchema(
        schema_name=schema_name,
        table_name=table_name,
        table_type=table_type,
        description=markdown_description,
        columns=col_list
    )
    
    # Set source_guid if a specific source_id was provided
    if source_id:
        schema_obj.source_guid = source_id
    
    # 7. Update Vector Store
    vector_store.insert_schema_embedding(schema_obj, embedding_text)
    
    # 8. Invalidate relationship graph cache (will be rebuilt on next query)
    invalidate_relationship_graph()
    
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
        # Invalidate relationship graph cache (will be rebuilt on next query)
        invalidate_relationship_graph()
        return True
    except Exception as e:
        print(f"Error syncing all schemas: {e}")
        raise

def parse_table_identifier(table_identifier: str, default_schema: str = "dbo") -> tuple[str, str]:
    """
    Parse a table identifier into schema and table name.
    
    Args:
        table_identifier: Table name in format 'table' or 'schema.table'
        default_schema: Default schema to use if not specified
    
    Returns:
        Tuple of (schema_name, table_name)
    """
    parts = table_identifier.strip().split('.')
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    elif len(parts) == 1:
        return default_schema, parts[0].strip()
    else:
        raise ValueError(f"Invalid table identifier format: {table_identifier}")

def validate_table_exists(engine, schema_name: str, table_name: str) -> tuple[bool, str, str]:
    """
    Validate if a table or view exists in the database.
    
    Args:
        engine: Database engine
        schema_name: Schema name
        table_name: Table or view name
    
    Returns:
        Tuple of (exists: bool, object_type: str, error_message: str)
    """
    try:
        inspector = inspect(engine)
        
        # Check if it's a table
        tables = inspector.get_table_names(schema=schema_name)
        if table_name in tables:
            return True, "table", ""
        
        # Check if it's a view
        views = inspector.get_view_names(schema=schema_name)
        if table_name in views:
            return True, "view", ""
        
        return False, "", f"Object '{schema_name}.{table_name}' not found in database"
    except Exception as e:
        return False, "", f"Error checking object '{schema_name}.{table_name}': {str(e)}"

def batch_sync_tables(table_identifiers: List[str], source_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Batch sync multiple tables from the database to the vector store.
    
    Args:
        table_identifiers: List of table names in format 'table' or 'schema.table'
        source_id: Optional data source ID for database connection
    
    Returns:
        Dictionary with sync results
    """
    engine = get_database_engine(source_id) if source_id else get_db_engine()
    results = []
    successful = 0
    failed = 0
    
    for identifier in table_identifiers:
        try:
            # Parse the identifier
            schema_name, table_name = parse_table_identifier(identifier)
            
            # Validate the object exists
            exists, obj_type, error_msg = validate_table_exists(engine, schema_name, table_name)
            
            if not exists:
                results.append({
                    "table_name": table_name,
                    "schema_name": schema_name,
                    "success": False,
                    "message": error_msg
                })
                failed += 1
                continue
            
            # Sync the table
            sync_specific_table(schema_name, table_name, source_id=source_id)
            results.append({
                "table_name": table_name,
                "schema_name": schema_name,
                "success": True,
                "message": f"Successfully synced {obj_type} '{schema_name}.{table_name}'"
            })
            successful += 1
            
        except ValueError as e:
            # Invalid format
            results.append({
                "table_name": identifier,
                "schema_name": "",
                "success": False,
                "message": str(e)
            })
            failed += 1
        except Exception as e:
            # Sync failed
            parts = identifier.split('.')
            t_name = parts[-1] if parts else identifier
            s_name = parts[0] if len(parts) == 2 else "dbo"
            results.append({
                "table_name": t_name,
                "schema_name": s_name,
                "success": False,
                "message": f"Error syncing table: {str(e)}"
            })
            failed += 1
    
    return {
        "total": len(table_identifiers),
        "successful": successful,
        "failed": failed,
        "results": results
    }

# --- Value Index Management ---

def ingest_values_from_excel(file_content: bytes, mode: str = "append", file_type: str = "xlsx", progress_callback=None, source_id: str = None) -> Dict[str, Any]:
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
        progress_callback: Optional callback function(current_row, total_rows) for progress tracking
    
    Returns:
        Dictionary with ingestion results
    """
    vector_store = get_vector_store()
    try:
        # Read file based on type
        if file_type.lower() == "csv":
            # Try multiple encodings for CSV files
            encodings = ["utf-8", "utf-8-sig", "cp1252", "latin1", "utf-16", "utf-16-le", "utf-16-be", "iso-8859-1", "windows-1252"]
            df = None
            last_error = None
            for encoding in encodings:
                try:
                    df = read_csv(io.BytesIO(file_content), encoding=encoding)
                    print(f"Successfully read CSV with encoding: {encoding}")
                    break
                except Exception as e:
                    print(f"Failed to read CSV with encoding {encoding}: {e}")
                    last_error = e
                    continue
            if df is None:
                # Try without specifying encoding as a last resort
                try:
                    df = read_csv(io.BytesIO(file_content), encoding='latin1', on_bad_lines='skip')
                    print("Successfully read CSV with latin1 and on_bad_lines='skip'")
                except Exception as e:
                    raise Exception(f"Unable to read CSV with any encoding. Last error: {last_error}. Final attempt error: {e}")
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
        
        # Ingest in batches
        success_count = 0
        total_rows = len(df)
        batch_size = 100
        
        # Prepare all items first (simple object creation is fast)
        all_items = []
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
                
                item = {
                    'value': str(row['value']),
                    'schema_name': str(row['schema_name']),
                    'table_name': str(row['table_name']),
                    'column_name': str(row['column_name']),
                    'metadata': metadata
                }
                all_items.append(item)
            except Exception as e:
                print(f"Failed to parse row {idx}: {e}")
                continue

        # Process batches
        for i in range(0, len(all_items), batch_size):
            batch = all_items[i:i + batch_size]
            try:
                vector_store.insert_value_items_batch(batch, source_guid=source_id)
                success_count += len(batch)
            except Exception as e:
                print(f"Failed to ingest batch {i // batch_size}: {e}")
                # Fallback to single insert if batch fails? 
                # For now just continue, assuming transient network/milvus issue or bad data
                continue
            
            # Call progress callback if provided
            if progress_callback:
                try:
                    progress_callback(success_count, total_rows)
                except:
                    pass  # Ignore callback errors
        
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

def clear_all_values(source_id: str = None) -> bool:
    """
    Clear values from the index, optionally filtered by source_id.
    """
    try:
        vector_store = get_vector_store()
        vector_store.clear_values_collection(source_id=source_id)
        return True
    except Exception as e:
        print(f"Error clearing values: {e}")
        return False
def ingest_schemas_from_excel(file_content: bytes, mode: str = "append", progress_callback=None, source_id: str = None) -> Dict[str, Any]:
    """
    Parse Excel file and ingest schema/table metadata.
    
    File format required (matches schema_index collection):
    - schema_name: Schema name (e.g., 'dbo')
    - table_name: Table or view name (e.g., 'Customers')
    - table_type: 'table' or 'view' (optional, defaults to 'table')
    - description: Rich Markdown description (also used for embedding)
    
    Args:
        file_content: Binary file content (Excel only)
        mode: "append" to add to existing schemas, "replace" to clear and reload
        progress_callback: Optional callback function(current_row, total_rows) for progress tracking
    
    Returns:
        Dictionary with ingestion results
    """
    vector_store = get_vector_store()
    try:
        # Read Excel file
        df = read_excel(io.BytesIO(file_content))
        
        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()
        
        # Validate columns - only schema_name, table_name, and description are required
        required_cols = ['schema_name', 'table_name', 'description']
        optional_cols = ['table_type']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            available_cols = df.columns.tolist()
            return {
                "status": "error",
                "message": f"File must contain columns: {', '.join(required_cols)}. Optional: {', '.join(optional_cols)}. Found: {', '.join(available_cols)}",
                "rows_processed": 0
            }
        
        # Add optional columns with defaults if missing
        if 'table_type' not in df.columns:
            df['table_type'] = 'table'
        
        # Select all relevant columns
        all_cols = required_cols + optional_cols
        df = df[all_cols]
        
        # Clean and deduplicate
        df['schema_name'] = df['schema_name'].astype(str).str.strip()
        df['table_name'] = df['table_name'].astype(str).str.strip()
        df['table_type'] = df['table_type'].astype(str).str.strip().str.lower()
        df['table_type'] = df['table_type'].apply(lambda x: x if x in ['table', 'view'] else 'table')
        df['description'] = df['description'].astype(str).str.strip()
        df = df.drop_duplicates(subset=['schema_name', 'table_name'])
        df = df[(df['schema_name'].notna()) & (df['schema_name'] != '') & 
                (df['table_name'].notna()) & (df['table_name'] != '') &
                (df['description'].notna()) & (df['description'] != '')]
        
        if df.empty:
            return {
                "status": "error",
                "message": "No valid schemas found in file",
                "rows_processed": 0
            }
        
        # If replacing, clear existing schemas first
        if mode == "replace":
            vector_store.clear_schemas_collection()
        
        # Ingest each row
        success_count = 0
        total_rows = len(df)
        for idx, row in df.iterrows():
            try:
                # Create schema object
                schema_obj = TableSchema(
                    schema_name=str(row['schema_name']),
                    table_name=str(row['table_name']),
                    table_type=str(row['table_type']),
                    description=str(row['description']),
                    columns=[]  # No columns in this import
                )
                
                # Set source_guid if provided
                if source_id:
                    schema_obj.source_guid = source_id
                
                # Insert into vector store - description is used for both embedding and storage
                text_for_embedding = str(row['description'])
                vector_store.insert_schema_embedding(schema_obj, text_for_embedding, str(row['table_type']))
                success_count += 1
            except Exception as e:
                print(f"Failed to ingest schema row {idx}: {e}")
                continue
            
            # Call progress callback if provided
            if progress_callback:
                try:
                    progress_callback(success_count, total_rows)
                except:
                    pass
        
        return {
            "status": "success",
            "message": f"Successfully ingested {success_count} schemas",
            "rows_processed": success_count,
            "total_rows": len(df)
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error processing file: {str(e)}",
            "rows_processed": 0
        }

def ingest_fewshots_from_excel(file_content: bytes, mode: str = "append", progress_callback=None, source_id: str = None) -> Dict[str, Any]:
    """
    Parse Excel file and ingest few-shot examples.
    
    File format required:
    - Column 1: question (natural language question)
    - Column 2: sql_query (correct SQL/R/SAS code)
    - Column 3 (optional): knowledge_type ("general", "sql_query", "r_code", "sas_code")
    
    Args:
        file_content: Binary file content (Excel only)
        mode: "append" to add to existing examples, "replace" to clear and reload
        progress_callback: Optional callback function(current_row, total_rows) for progress tracking
    
    Returns:
        Dictionary with ingestion results
    """
    vector_store = get_vector_store()
    try:
        # Read Excel file
        df = read_excel(io.BytesIO(file_content))
        
        #  Normalize column names
        df.columns = df.columns.str.strip().str.lower()
        
        # Validate columns
        required_cols = ['question', 'sql_query']
        optional_cols = ['knowledge_type']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            available_cols = df.columns.tolist()
            return {
                "status": "error",
                "message": f"File must contain columns: {', '.join(required_cols)}. Optional: {', '.join(optional_cols)}. Found: {', '.join(available_cols)}",
                "rows_processed": 0
            }
        
        # Add knowledge_type with default if not present
        if 'knowledge_type' not in df.columns:
            df['knowledge_type'] = 'sql_query'
        
        # Select all relevant columns
        all_cols = required_cols + ['knowledge_type']
        df = df[all_cols]
        
        # Clean and deduplicate
        df['question'] = df['question'].astype(str).str.strip()
        df['sql_query'] = df['sql_query'].astype(str).str.strip()
        df['knowledge_type'] = df['knowledge_type'].fillna('sql_query').astype(str).str.strip().str.lower()
        # Validate knowledge_type values
        valid_types = ['general', 'sql_query', 'r_code', 'sas_code']
        df['knowledge_type'] = df['knowledge_type'].apply(lambda x: x if x in valid_types else 'sql_query')
        
        df = df.drop_duplicates(subset=['question'])
        df = df[(df['question'].notna()) & (df['question'] != '') & 
                (df['sql_query'].notna()) & (df['sql_query'] != '')]
        
        if df.empty:
            return {
                "status": "error",
                "message": "No valid few-shot examples found in file",
                "rows_processed": 0
            }
        
        # If replacing, clear existing fewshots first
        if mode == "replace":
            vector_store.clear_fewshots_collection()
        
        # Ingest each row
        success_count = 0
        total_rows = len(df)
        for idx, row in df.iterrows():
            try:
                # Insert fewshot example with knowledge_type
                vector_store.insert_fewshot_item(
                    question=str(row['question']),
                    sql_query=str(row['sql_query']),
                    knowledge_type=str(row['knowledge_type']),
                    source_guid=source_id
                )
                success_count += 1
            except Exception as e:
                print(f"Failed to ingest fewshot row {idx}: {e}")
                continue
            
            # Call progress callback if provided
            if progress_callback:
                try:
                    progress_callback(success_count, total_rows)
                except:
                    pass
        
        return {
            "status": "success",
            "message": f"Successfully ingested {success_count} few-shot examples",
            "rows_processed": success_count,
            "total_rows": len(df)
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error processing file: {str(e)}",
            "rows_processed": 0
        }

def clear_all_schemas_data(source_id: str = None) -> bool:
    """
    Clear schemas from the vector store, optionally filtered by source_id.
    """
    try:
        vector_store = get_vector_store()
        vector_store.clear_schemas_collection(source_id=source_id)
        vector_store.clear_schemas_v2_collection(source_id=source_id)
        return True
    except Exception as e:
        print(f"Error clearing schemas: {e}")
        return False
