"""
Schema Scan Service - Connects to a SQL Server database, discovers all objects,
and automatically generates skill files (markdown schemas, data groups, indices).
"""

import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import create_engine, inspect, text
import urllib.parse

from app.services.settings_service import build_connection_string
from app.services.ingest_service import (
    clean_column_type,
    get_foreign_key_map,
    get_primary_key_columns,
    get_table_description,
    build_table_markdown_description,
)

logger = logging.getLogger(__name__)

SKILLS_BASE_PATH = Path("skills/data-sources")

# System schemas to skip during scan
SYSTEM_SCHEMAS = frozenset([
    "information_schema", "sys", "guest", "sysadmin",
    "db_owner", "db_accessadmin", "db_securityadmin",
    "db_ddladmin", "db_backupoperator", "db_datareader",
    "db_datawriter", "db_denydatareader", "db_denydatawriter",
])


def _slugify(name: str) -> str:
    """Convert name to filesystem-safe slug"""
    return re.sub(r'[^\w\s-]', '', name.lower()).replace(' ', '-')


def _build_engine(server: str, database: str, auth_type: str = "windows",
                  driver: str = "ODBC Driver 17 for SQL Server",
                  username: str = None, password: str = None,
                  trust_server_certificate: bool = True):
    """Build a SQLAlchemy engine from connection parameters."""
    conn_str = build_connection_string(
        driver=driver,
        server=server,
        database=database,
        auth_type=auth_type,
        username=username,
        password=password,
        trust_server_certificate=trust_server_certificate,
    )
    sa_url = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(conn_str)}"
    return create_engine(sa_url)


def scan_database_objects(
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
) -> Dict[str, Any]:
    """
    Scan a SQL Server database and generate skill files for all discovered objects.

    Returns a summary dict with counts of schemas, tables, views created.
    """
    if keywords is None:
        keywords = []

    ds_slug = _slugify(data_source_name)
    ds_dir = SKILLS_BASE_PATH / ds_slug

    if not ds_dir.exists():
        raise ValueError(f"Data source directory not found: {ds_dir}")

    # ---- Connect ----
    engine = _build_engine(
        server=server,
        database=database,
        auth_type=auth_type,
        driver=driver,
        username=username,
        password=password,
        trust_server_certificate=trust_server_certificate,
    )

    # Quick connectivity check
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    logger.info(f"Connected to {server}/{database} for schema scan")

    inspector = inspect(engine)

    # ---- Discover schemas + objects ----
    schemas_found = inspector.get_schema_names()
    schemas_found = [s for s in schemas_found if s.lower() not in SYSTEM_SCHEMAS]

    schemas_dir = ds_dir / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)

    total_tables = 0
    total_views = 0
    schema_summaries: List[Dict] = []
    all_objects_index: Dict[str, List[Dict]] = {}  # schema -> list of object metadata

    for schema_name in schemas_found:
        table_names = inspector.get_table_names(schema=schema_name)
        view_names = inspector.get_view_names(schema=schema_name)

        if not table_names and not view_names:
            continue  # skip empty schemas

        schema_folder = schemas_dir / schema_name
        schema_folder.mkdir(parents=True, exist_ok=True)

        objects_in_schema: List[Dict] = []

        # Process tables and views
        all_objects = [(n, "table") for n in table_names] + [(n, "view") for n in view_names]

        for obj_name, obj_type in all_objects:
            try:
                md_content, obj_meta = _build_object_markdown(
                    engine, inspector, schema_name, obj_name, obj_type, data_source_name
                )

                # Write markdown file
                file_name = f"{schema_name}.{obj_name}.md"
                md_file = schema_folder / file_name
                md_file.write_text(md_content, encoding="utf-8")

                obj_meta["file_name"] = file_name
                objects_in_schema.append(obj_meta)

                if obj_type == "table":
                    total_tables += 1
                else:
                    total_views += 1

                logger.debug(f"  Created {obj_type} {schema_name}.{obj_name}")
            except Exception as e:
                logger.warning(f"  Failed to process {schema_name}.{obj_name}: {e}")

        # Write .object-index.json for this schema
        object_index = {
            "schema": schema_name,
            "total_objects": len(objects_in_schema),
            "tables": sum(1 for o in objects_in_schema if o["object_type"] == "Table"),
            "views": sum(1 for o in objects_in_schema if o["object_type"] == "View"),
            "objects": objects_in_schema,
        }
        idx_file = schema_folder / ".object-index.json"
        idx_file.write_text(json.dumps(object_index, indent=2, ensure_ascii=False), encoding="utf-8")

        all_objects_index[schema_name] = objects_in_schema
        schema_summaries.append({
            "schema_name": schema_name,
            "description": f"Contains {len(table_names)} tables and {len(view_names)} views",
            "object_index_file": f"schemas/{schema_name}/.object-index.json",
            "total_objects": len(objects_in_schema),
            "tables": len(table_names),
            "views": len(view_names),
        })

    # ---- Write .schema-index.json ----
    schema_index = {
        "data_source": data_source_name,
        "total_schemas": len(schema_summaries),
        "schemas": schema_summaries,
    }
    (ds_dir / ".schema-index.json").write_text(
        json.dumps(schema_index, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ---- Auto-generate data groups (one per schema) ----
    _generate_data_groups(ds_dir, data_source_name, all_objects_index)

    # ---- Update _data-source.md with Server/Database if missing ----
    _ensure_connection_fields(ds_dir, server, database)

    engine.dispose()

    summary = {
        "data_source": data_source_name,
        "schemas_scanned": len(schema_summaries),
        "tables_created": total_tables,
        "views_created": total_views,
        "total_objects": total_tables + total_views,
    }
    logger.info(f"Scan complete: {summary}")
    return summary


def _build_object_markdown(
    engine, inspector, schema_name: str, obj_name: str,
    obj_type: str, data_source_name: str
) -> Tuple[str, Dict]:
    """
    Build the full markdown file content and metadata dict for a single DB object.
    """
    columns = inspector.get_columns(obj_name, schema=schema_name)

    fk_map = get_foreign_key_map(inspector, obj_name, schema_name) if obj_type == "table" else {}
    pk_columns = get_primary_key_columns(inspector, obj_name, schema_name) if obj_type == "table" else []
    db_description = get_table_description(engine, obj_name, schema_name, obj_type)

    if not db_description:
        db_description = f"Stores {obj_name} data."

    # Use the existing rich-markdown builder from ingest_service
    markdown_body = build_table_markdown_description(
        schema_name=schema_name,
        table_name=obj_name,
        table_description=db_description,
        columns=columns,
        fk_map=fk_map,
        pk_columns=pk_columns,
        table_type=obj_type,
    )

    # Wrap with skill-file header
    type_label = obj_type.capitalize()
    content = f"""# {type_label}: [{schema_name}].[{obj_name}]

**Data Source:** {data_source_name}
**Schema:** {schema_name}
**Type:** {type_label}

## Description

{markdown_body}
"""

    # Build metadata for the object index
    # Extract keywords from description + object name
    kw_words = re.findall(r'[A-Z][a-z]+|[a-z]+', obj_name)
    keywords = list(dict.fromkeys([w.lower() for w in kw_words if len(w) > 2]))[:8]

    meta = {
        "object_type": type_label,
        "schema_name": schema_name,
        "object_name": obj_name,
        "description": db_description,
        "keywords": keywords,
    }
    return content, meta


def _generate_data_groups(ds_dir: Path, data_source_name: str, all_objects_index: Dict[str, List[Dict]]):
    """
    Generate one data-group per schema (auto-generated).
    """
    data_groups_dir = ds_dir / "data-groups"
    data_groups_dir.mkdir(parents=True, exist_ok=True)
    data_groups_entries: List[str] = []

    for schema_name, objects in all_objects_index.items():
        if not objects:
            continue

        group_name = f"{schema_name.capitalize()} Schema Objects"
        group_filename = f"_{_slugify(schema_name)}-group.md"
        group_file = data_groups_dir / group_filename

        # Collect keywords from all objects in the group
        all_keywords = set()
        for obj in objects:
            all_keywords.update(obj.get("keywords", []))
        keywords_str = ", ".join(sorted(all_keywords)[:20])

        # Build object links
        object_links = []
        for obj in objects:
            s = obj["schema_name"]
            n = obj["object_name"]
            t = obj["object_type"]
            object_links.append(f"- **[{s}.{n}](../schemas/{s}/{s}.{n}.md)** - {t}")

        content = f"""# {group_name}

**Data Source:** {data_source_name}
**Category:** Auto-generated
**Keywords:** {keywords_str}

## Description

Auto-generated data group for the [{schema_name}] schema.

## Data Objects

{chr(10).join(object_links)}
"""
        group_file.write_text(content, encoding="utf-8")
        data_groups_entries.append(f"{group_name}|{group_filename}")
        logger.debug(f"  Created data group: {group_name}")

    # Write .data-groups index
    dg_file = ds_dir / ".data-groups"
    # Preserve existing entries if any
    existing_entries = set()
    if dg_file.exists():
        for line in dg_file.read_text(encoding="utf-8").strip().splitlines():
            if line.strip():
                existing_entries.add(line.strip())

    for entry in data_groups_entries:
        existing_entries.add(entry)

    dg_file.write_text("\n".join(sorted(existing_entries)) + "\n", encoding="utf-8")


def _ensure_connection_fields(ds_dir: Path, server: str, database: str):
    """
    Make sure _data-source.md contains **Server:** and **Database:** fields.
    """
    ds_file = ds_dir / "_data-source.md"
    if not ds_file.exists():
        return

    content = ds_file.read_text(encoding="utf-8")
    modified = False

    if "**Server:**" not in content:
        # Insert after **Type:** line
        content = re.sub(
            r'(\*\*Type:\*\*\s*[^\n]*\n)',
            f'\\1**Server:** {server}\n**Database:** {database}\n',
            content,
            count=1,
        )
        modified = True
    else:
        # Update existing Server/Database
        content = re.sub(r'\*\*Server:\*\*\s*[^\n]*', f'**Server:** {server}', content)
        content = re.sub(r'\*\*Database:\*\*\s*[^\n]*', f'**Database:** {database}', content)
        modified = True

    if modified:
        ds_file.write_text(content, encoding="utf-8")
