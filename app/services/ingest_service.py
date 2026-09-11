
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text, inspect
from openai import OpenAI
from app.core.config import settings
from app.services.settings_service import load_settings
from app.core.database import get_database_engine


def _resolve_source_guid_from_skills() -> str:
    """
    Attempt to resolve a source GUID from skills data sources.
    Falls back to "legacy" when no skills data is present.
    """
    try:
        from app.services.skills_service import SkillsService
        skills_service = SkillsService()
        primary = skills_service.load_primary_data_source()
        if primary and getattr(primary, "source_id", None):
            return primary.source_id
        sources = skills_service.load_data_sources_index()
        for source in sources:
            if getattr(source, "source_id", None):
                return source.source_id
    except Exception:
        pass
    return "legacy"


def _normalize_exclude_name(raw_name: str) -> Tuple[Optional[str], str]:
    """
    Normalize an exclusion name to (schema, object) or (None, object).

    Supports names like:
    - dbo.TableName
    - [dbo].[TableName]
    - TableName
    """
    cleaned = raw_name.strip().replace("[", "").replace("]", "")
    cleaned = cleaned.replace('"', "").replace("'", "").strip()
    if not cleaned:
        return None, ""

    parts = [p for p in cleaned.split(".") if p]
    if len(parts) >= 2:
        schema_name = parts[-2].lower()
        object_name = parts[-1].lower()
        return schema_name, object_name
    return None, parts[0].lower()


def _resolve_exclude_dir(source_id: Optional[str]) -> Optional[Path]:
    """Resolve skills data source directory for exclusion list lookup."""
    try:
        from app.services.skills_service import get_skills_service
        skills_service = get_skills_service()

        if source_id:
            sources = skills_service.load_data_sources_index()
            target = None
            for source in sources:
                if source.source_id == source_id:
                    target = source
                    break
            if not target:
                for source in sources:
                    if (source.name or "").lower() == source_id.lower():
                        target = source
                        break
        else:
            target = skills_service.load_primary_data_source()

        if not target or not getattr(target, "name", None):
            return None

        slug = re.sub(r"[^\w\s-]", "", target.name.lower()).replace(" ", "-")
        return Path("skills/data-sources") / slug
    except Exception:
        return None


def _load_exclude_list(source_id: Optional[str]) -> Tuple[frozenset, frozenset]:
    """Load exclusion list for the given source_id (if present)."""
    ds_dir = _resolve_exclude_dir(source_id)
    if not ds_dir:
        return frozenset(), frozenset()

    exclude_file = ds_dir / "exclude_objects.txt"
    if not exclude_file.exists():
        return frozenset(), frozenset()

    qualified = set()
    unqualified = set()
    for line in exclude_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            schema_name, object_name = _normalize_exclude_name(stripped)
            if not object_name:
                continue
            if schema_name:
                qualified.add(f"{schema_name}.{object_name}")
            else:
                unqualified.add(object_name)
    return frozenset(qualified), frozenset(unqualified)


def _is_excluded(
    schema_name: str,
    object_name: str,
    exclude_qualified: frozenset,
    exclude_unqualified: frozenset,
) -> bool:
    """Check whether an object should be excluded by name."""
    obj_lower = object_name.lower()
    if obj_lower in exclude_unqualified:
        return True
    qualified = f"{schema_name.lower()}.{obj_lower}"
    return qualified in exclude_qualified

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
        api_key = settings.EMBEDDING_API_KEY or settings.LLM_API_KEY

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
                "or provide EMBEDDING_API_KEY/LLM_API_KEY in the environment."
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
    """Ensure contract collections exist."""
    from app.services.stores.provider_factory import get_vector_provider

    provider = get_vector_provider()
    if hasattr(provider, "ensure_schema"):
        provider.ensure_schema()
    print("Ensured contract Milvus collections.")

def ingest_metadata(source_id: Optional[str] = None):
    from app.services.stores.provider_factory import get_vector_provider
    from app.services.stores.schema_rows import build_schema_object_rows, delete_schema_object_rows

    engine = get_database_engine(source_id)
    inspector = inspect(engine)
    provider = get_vector_provider()
    if hasattr(provider, "ensure_schema"):
        provider.ensure_schema()

    schemas = inspector.get_schema_names()
    data_source_id = source_id or _resolve_source_guid_from_skills()

    exclude_qualified, exclude_unqualified = _load_exclude_list(source_id)
    exclude_count = len(exclude_qualified) + len(exclude_unqualified)
    if exclude_count:
        print(f"Loaded {exclude_count} excluded object(s) from exclude_objects.txt")

    print("Extracting metadata...")

    existing_items = set()
    try:
        for row in provider.fetch_all("schemas", data_source_id):
            if (row.get("entity_type") or "Table") == "Column":
                continue
            existing_items.add((row.get("schema_name"), row.get("object_name")))
        print(f"Found {len(existing_items)} existing tables in vector store for source {data_source_id}.")
    except Exception as e:
        print(f"Warning: Could not check existing items: {e}")

    upsert_rows = []
    for schema in schemas:
        if schema in ['information_schema', 'sys', 'guest', 'sysadmin']:
            continue

        table_names = inspector.get_table_names(schema=schema)
        view_names = inspector.get_view_names(schema=schema)
        objects_to_process = [(name, 'table') for name in table_names] + [(name, 'view') for name in view_names]

        for obj_name, obj_type in objects_to_process:
            if _is_excluded(schema, obj_name, exclude_qualified, exclude_unqualified):
                if (schema, obj_name) in existing_items:
                    try:
                        delete_schema_object_rows(provider, data_source_id, schema, obj_name)
                        print(f"Deleted excluded {schema}.{obj_name} from vector store")
                    except Exception as del_e:
                        print(f"Error deleting excluded {schema}.{obj_name}: {del_e}")
                else:
                    print(f"Skipping excluded {schema}.{obj_name}")
                continue

            if (schema, obj_name) in existing_items:
                print(f"Item {schema}.{obj_name} exists. Deleting to replace...")
                try:
                    delete_schema_object_rows(provider, data_source_id, schema, obj_name)
                except Exception as del_e:
                    print(f"Error deleting {schema}.{obj_name}: {del_e}")

            columns = inspector.get_columns(obj_name, schema=schema)
            fk_map = get_foreign_key_map(inspector, obj_name, schema) if obj_type == 'table' else {}
            pk_columns = get_primary_key_columns(inspector, obj_name, schema) if obj_type == 'table' else []

            col_list = []
            for col in columns:
                col_list.append({
                    "name": col['name'],
                    "data_type": clean_column_type(col['type']),
                    "description": col.get('comment', '')
                })

            db_description = get_table_description(engine, obj_name, schema, obj_type)
            obj_description = db_description if db_description else f" -- stores {obj_name} data."

            markdown_description = build_table_markdown_description(
                schema_name=schema,
                table_name=obj_name,
                table_description=obj_description,
                columns=columns,
                fk_map=fk_map,
                pk_columns=pk_columns,
                table_type=obj_type
            )

            try:
                upsert_rows.extend(
                    build_schema_object_rows(
                        provider,
                        data_source_id,
                        schema,
                        obj_name,
                        obj_type,
                        markdown_description,
                        col_list,
                    )
                )
                print(f"Processed {obj_type} {schema}.{obj_name}")
            except Exception as e:
                print(f"Failed to embed {obj_type} {schema}.{obj_name}: {e}")

    if upsert_rows:
        print(f"Inserting {len(upsert_rows)} parent/column rows into schemas...")
        provider.upsert("schemas", upsert_rows)
        print("Ingestion complete (schemas).")
    else:
        print("No data found to ingest.")
