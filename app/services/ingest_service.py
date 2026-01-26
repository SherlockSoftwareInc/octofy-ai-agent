
import json
from typing import List, Dict, Any
from sqlalchemy import create_engine, text, inspect
from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
from openai import OpenAI
from app.core.config import settings
from app.services.settings_service import load_settings
import urllib.parse

from app.core.database import get_db_engine

# --- Configuration ---
EMBEDDING_DIM = 1536 # text-embedding-3-small

def _resolve_embedding_config() -> tuple[OpenAI, str]:
    """
    Resolve embedding client and model from saved agent settings.
    Falls back to env vars, but errors on placeholder keys unless a custom endpoint is set.
    """
    agent_settings = load_settings()
    llm_config = agent_settings.llm_config
    vector_config = agent_settings.vector_config

    embedding_config = agent_settings.embedding_config
    embedding_model = embedding_config.model or "text-embedding-3-small"

    # Prioritize embedding specific config
    api_key = embedding_config.api_key
    base_url = embedding_config.base_url

    # Fallback to env var if no key configured and provider is openai (or default)
    if not api_key:
         api_key = settings.OPENAI_API_KEY

    # If still no key, and LLM is OpenAI-compatible, maybe we share? 
    # But dangerous if LLM is DeepSeek and Embed is OpenAI. 
    # Better to be strict: if Embed Provider is OpenAI, we need OpenAI key.
    
    # Treat placeholder keys as missing
    invalid_key = not api_key or (str(api_key).startswith("sk-") and len(str(api_key)) < 20)
    
    if invalid_key:
        # If we have a base_url (local/custom), we might allow dummy key
        if base_url:
             api_key = "dummy-key"
        else:
             raise RuntimeError(
                "Embedding API key is not configured. Set it in Settings > Embedding Configuration "
                "or provide OPENAI_API_KEY in the environment."
            )

    return OpenAI(api_key=api_key, base_url=base_url), embedding_model

# Use shared get_db_engine instead of internal one


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


def get_primary_key_columns(inspector, table_name: str, schema_name: str) -> List[str]:
    """
    Get primary key column names for a table.
    
    Returns:
        List of column names that are part of the primary key.
    """
    pk_columns = []
    try:
        pk_constraint = inspector.get_pk_constraint(table_name, schema=schema_name)
        if pk_constraint:
            pk_columns = pk_constraint.get('constrained_columns', [])
    except Exception as e:
        print(f"Warning: Could not retrieve primary key for {schema_name}.{table_name}: {e}")
    
    return pk_columns


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
    pk_columns: List[str] = None,
    table_type: str = "table"
) -> str:
    """
    Build a rich Markdown description for a table or view.
    
    Format:
    # **Table:** `[schema].[table]`  (or **View:** for views)
    > description
    ---
    ### **Columns:**
    | Ord | Name | Data Type | Description |
    ...
    ---
    """
    if pk_columns is None:
        pk_columns = []
    
    # Header - use capitalized table_type (Table or View)
    type_label = table_type.capitalize() if table_type else "Table"
    md = f"# **{type_label}:** `[{schema_name}].[{table_name}]`\n"
    md += f"> {table_description}\n"
    md += "---\n"
    md += "### **Columns:**\n"
    md += "| Ord | Name | Data Type | Description |\n"
    md += "|:---:|:---:|:---:|:---|\n"
    
    # Column rows
    for idx, col in enumerate(columns, start=1):
        col_name = col.get('name', '')
        col_type = clean_column_type(col.get('type', col.get('data_type', '')))
        col_desc = col.get('description', '') or col.get('comment', '') or ''
        
        # Build description parts
        desc_parts = []
        
        # Add primary key indicator for table primary key columns
        if table_type == 'table' and col_name in pk_columns:
            desc_parts.append('Primary key')
        
        # Add existing description if present
        if col_desc:
            desc_parts.append(col_desc.rstrip())
        
        # Add FK reference if present (and not already in description)
        if col_name in fk_map and 'Reference:' not in col_desc:
            desc_parts.append(f"Reference: {fk_map[col_name]}")
        
        # Join all parts with comma
        final_desc = ', '.join(desc_parts) if desc_parts else ''
        
        md += f"| {idx} | `{col_name}` | {col_type} | {final_desc} |\n"
    
    md += "---\n"
    return md

def create_milvus_collections():
    vector_config = load_settings().vector_config
    connections.connect(host=vector_config.host, port=vector_config.port)
    
    # 1. Schema Index
    if utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA):
        utility.drop_collection(settings.MILVUS_COLLECTION_SCHEMA)
        
    schema_fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema(name="schema_name", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="table_name", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="table_type", dtype=DataType.VARCHAR, max_length=32),  # 'table' or 'view'
        FieldSchema(name="description", dtype=DataType.VARCHAR, max_length=65535)  # Rich Markdown description (also used for embedding)
    ]
    schema_schema = CollectionSchema(fields=schema_fields, description="Database Schema Index")
    schema_coll = Collection(name=settings.MILVUS_COLLECTION_SCHEMA, schema=schema_schema)
    
    # Create Index
    index_params = {
        "metric_type": "L2",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 1024}
    }
    schema_coll.create_index(field_name="embedding", index_params=index_params)
    print(f"Created collection: {settings.MILVUS_COLLECTION_SCHEMA}")

    # 2. Few-shot Index / Knowledge Base
    if utility.has_collection(settings.MILVUS_COLLECTION_FEWSHOT):
        utility.drop_collection(settings.MILVUS_COLLECTION_FEWSHOT)
        
    fs_fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="sql_query", dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="knowledge_type", dtype=DataType.VARCHAR, max_length=32)
    ]
    fs_schema = CollectionSchema(fields=fs_fields, description="Knowledge Base Index")
    fs_coll = Collection(name=settings.MILVUS_COLLECTION_FEWSHOT, schema=fs_schema)
    fs_coll.create_index(field_name="embedding", index_params=index_params)
    print(f"Created collection: {settings.MILVUS_COLLECTION_FEWSHOT}")
    
    # 3. Value Index (Stub)
    if utility.has_collection(settings.MILVUS_COLLECTION_VALUES):
        utility.drop_collection(settings.MILVUS_COLLECTION_VALUES)
        
    # Value index must align with vector_store.insert_value_item expectations
    val_fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema(name="value", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="schema_name", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="table_name", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="column_name", dtype=DataType.VARCHAR, max_length=128)
    ]
    val_schema = CollectionSchema(fields=val_fields, description="Lookup Value Index")
    val_coll = Collection(name=settings.MILVUS_COLLECTION_VALUES, schema=val_schema)
    val_coll.create_index(field_name="embedding", index_params=index_params)
    print(f"Created collection: {settings.MILVUS_COLLECTION_VALUES}")

    # 4. Contribution Library (Staging Area for User Contributions)
    if utility.has_collection(settings.MILVUS_COLLECTION_CONTRIBUTIONS):
        utility.drop_collection(settings.MILVUS_COLLECTION_CONTRIBUTIONS)
        
    contrib_fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema(name="question", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="sql_query", dtype=DataType.VARCHAR, max_length=4096),
        FieldSchema(name="knowledge_type", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="submitted_at", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="status", dtype=DataType.VARCHAR, max_length=32)
    ]
    contrib_schema = CollectionSchema(fields=contrib_fields, description="Contribution Library - Staging Area")
    contrib_coll = Collection(name=settings.MILVUS_COLLECTION_CONTRIBUTIONS, schema=contrib_schema)
    contrib_coll.create_index(field_name="embedding", index_params=index_params)
    print(f"Created collection: {settings.MILVUS_COLLECTION_CONTRIBUTIONS}")

def ingest_metadata():
    engine = get_db_engine()
    inspector = inspect(engine)
    client, embedding_model = _resolve_embedding_config()
    
    schemas = inspector.get_schema_names()
    
    data_rows = []
    
    print("Extracting metadata...")
    
    # Check for existing items to avoid duplicates
    existing_items = set()
    search_collection = None
    try:
        vector_config = load_settings().vector_config
        connections.connect(host=vector_config.host, port=vector_config.port)
        if utility.has_collection(settings.MILVUS_COLLECTION_SCHEMA):
            search_collection = Collection(settings.MILVUS_COLLECTION_SCHEMA)
            search_collection.load()
            
            # Query all existing schema_name and table_name
            # Limit to 10000 for now, assuming we don't have massive schema counts yet
            results = search_collection.query(
                expr="", 
                output_fields=["schema_name", "table_name"],
                limit=10000
            )
            
            for res in results:
                existing_items.add((res['schema_name'], res['table_name']))
            
            print(f"Found {len(existing_items)} existing tables in vector store.")
    except Exception as e:
        print(f"Warning: Could not check existing items: {e}")
        
    for schema in schemas:
        if schema in ['information_schema', 'sys', 'guest', 'sysadmin']: continue # Skip system schemas
        
        # Get both tables and views
        table_names = inspector.get_table_names(schema=schema)
        view_names = inspector.get_view_names(schema=schema)
        
        # Process tables and views together with their type
        objects_to_process = [(name, 'table') for name in table_names] + [(name, 'view') for name in view_names]
        
        for obj_name, obj_type in objects_to_process:
            # Check if already exists
            if (schema, obj_name) in existing_items:
                print(f"Item {schema}.{obj_name} exists. Deleting to replace...")
                try:
                    if search_collection:
                        expr = f'schema_name == "{schema}" and table_name == "{obj_name}"'
                        search_collection.delete(expr)
                except Exception as del_e:
                    print(f"Error deleting {schema}.{obj_name}: {del_e}")
            
            # Get columns
            columns = inspector.get_columns(obj_name, schema=schema)
            
            # Get foreign key mappings (only applicable for tables, views don't have FKs)
            fk_map = get_foreign_key_map(inspector, obj_name, schema) if obj_type == 'table' else {}
            
            # Get primary key columns (only applicable for tables)
            pk_columns = get_primary_key_columns(inspector, obj_name, schema) if obj_type == 'table' else []
            
            # Build column info list
            col_list = []
            for col in columns:
                col_info = {
                    "name": col['name'],
                    "data_type": clean_column_type(col['type']),
                    "description": col.get('comment', '')
                }
                col_list.append(col_info)
            
            # Get description from database extended properties
            db_description = get_table_description(engine, obj_name, schema, obj_type)
            
            # Use DB description if available, otherwise generate default
            if db_description:
                obj_description = db_description
            else:
                obj_description = f" -- stores {obj_name} data."
            
            # Build embedding text: [name] + [description]
            # Simple and semantic - no column counts
            full_text = f"{obj_type}: {obj_name}. {obj_description}"
            
            # Create rich Markdown description
            markdown_description = build_table_markdown_description(
                schema_name=schema,
                table_name=obj_name,
                table_description=obj_description,
                columns=columns,
                fk_map=fk_map,
                pk_columns=pk_columns,
                table_type=obj_type
            )

            # Generate Embedding using the markdown description
            try:
                embedding = client.embeddings.create(input=[markdown_description], model=embedding_model).data[0].embedding

                data_rows.append({
                    "schema_name": schema,
                    "table_name": obj_name,
                    "table_type": obj_type,  # 'table' or 'view'
                    "description": markdown_description, # Rich Markdown description (also used for embedding)
                    "embedding": embedding
                })
                print(f"Processed {obj_type} {schema}.{obj_name}")
            except Exception as e:
                print(f"Failed to embed {obj_type} {schema}.{obj_name}: {e}")

    if data_rows:
        vector_config = load_settings().vector_config
        connections.connect(host=vector_config.host, port=vector_config.port)
        print(f"Inserting {len(data_rows)} rows into Milvus...")
        collection = Collection(settings.MILVUS_COLLECTION_SCHEMA)
        
        # Column-based organization
        c_embeddings = [r['embedding'] for r in data_rows]
        c_schemas = [r['schema_name'] for r in data_rows]
        c_tables = [r['table_name'] for r in data_rows]
        c_table_types = [r['table_type'] for r in data_rows]
        c_descs = [r['description'] for r in data_rows]
        
        collection.insert([c_embeddings, c_schemas, c_tables, c_table_types, c_descs])
        collection.flush()
        print("Ingestion complete.")
    else:
        print("No data found to ingest.")
