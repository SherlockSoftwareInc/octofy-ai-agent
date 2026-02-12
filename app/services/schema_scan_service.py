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
from app.services.object_discovery_service import (
    discover_functions,
    build_function_markdown_description,
)

logger = logging.getLogger(__name__)

SKILLS_BASE_PATH = Path("skills/data-sources")

# Common stop words excluded from keyword extraction
KEYWORD_STOP_WORDS = frozenset([
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
    'to', 'for', 'of', 'with', 'by',
])

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


def _extract_keywords(object_name: str, description: str = "") -> list:
    """
    Extract up to 8 unique keywords from an object name and its description.

    Words from the description are filtered by length (>3 chars) and stop words,
    then combined with CamelCase/snake_case parts of the object name.
    """
    keywords: list = []
    if description:
        words = re.findall(r'\b\w+\b', description.lower())
        keywords = [w for w in words if len(w) > 3 and w not in KEYWORD_STOP_WORDS][:5]
    name_parts = re.findall(r'[A-Z][a-z]+|[a-z]+', object_name)
    keywords.extend([p.lower() for p in name_parts if len(p) > 2])
    return list(dict.fromkeys(keywords))[:8]


def _build_usage_example(schema_name: str, object_name: str, parameters: list) -> str:
    """
    Build a SQL usage example string for a function.

    Note: object_discovery_service.build_function_markdown_description() contains
    equivalent inline logic for its Markdown output. If the format changes, update
    both locations.
    """
    if parameters:
        param_list = ", ".join([f"{p['name']} = <value>" for p in parameters])
        return f"SELECT [{schema_name}].[{object_name}]({param_list})"
    return f"SELECT [{schema_name}].[{object_name}]()"


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
    total_functions = 0
    schema_summaries: List[Dict] = []
    all_objects_index: Dict[str, List[Dict]] = {}  # schema -> list of object metadata

    for schema_name in schemas_found:
        table_names = inspector.get_table_names(schema=schema_name)
        view_names = inspector.get_view_names(schema=schema_name)

        # Discover functions for this schema (before the guard so function-only
        # schemas are not skipped)
        func_objects = []
        try:
            func_objects = discover_functions(engine, schema=schema_name)
        except Exception as e:
            logger.warning(f"  Failed to discover functions for schema {schema_name}: {e}")

        if not table_names and not view_names and not func_objects:
            continue  # skip truly empty schemas

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

        # Process functions (already discovered above)
        for func in func_objects:
            try:
                md_content = build_function_markdown_description(func)
                # Use "fn." prefix to avoid filename collisions with tables/views
                file_name = f"{schema_name}.fn.{func.object_name}.md"
                md_file = schema_folder / file_name
                md_file.write_text(md_content, encoding="utf-8")

                func_keywords = _extract_keywords(func.object_name, func.description or "")
                usage_example = _build_usage_example(
                    schema_name, func.object_name, func.parameters or []
                )

                obj_meta = {
                    "object_type": "Function",
                    "schema_name": schema_name,
                    "object_name": func.object_name,
                    "description": func.description or "",
                    "keywords": func_keywords,
                    "file_name": file_name,
                    "usage_example": usage_example,
                }

                objects_in_schema.append(obj_meta)
                total_functions += 1
                logger.debug(f"  Created function {schema_name}.{func.object_name}")
            except Exception as e:
                logger.warning(f"  Failed to process function {schema_name}.{func.object_name}: {e}")

        # Write .object-index.json for this schema
        schema_table_count = sum(1 for o in objects_in_schema if o["object_type"] == "Table")
        schema_view_count = sum(1 for o in objects_in_schema if o["object_type"] == "View")
        schema_func_count = sum(1 for o in objects_in_schema if o["object_type"] == "Function")
        object_index = {
            "schema": schema_name,
            "total_objects": len(objects_in_schema),
            "tables": schema_table_count,
            "views": schema_view_count,
            "functions": schema_func_count,
            "objects": objects_in_schema,
        }
        idx_file = schema_folder / ".object-index.json"
        idx_file.write_text(json.dumps(object_index, indent=2, ensure_ascii=False), encoding="utf-8")

        all_objects_index[schema_name] = objects_in_schema
        parts = []
        if schema_table_count:
            parts.append(f"{schema_table_count} tables")
        if schema_view_count:
            parts.append(f"{schema_view_count} views")
        if schema_func_count:
            parts.append(f"{schema_func_count} functions")
        schema_summaries.append({
            "schema_name": schema_name,
            "description": f"Contains {', '.join(parts)}" if parts else "Empty schema",
            "object_index_file": f"schemas/{schema_name}/.object-index.json",
            "total_objects": len(objects_in_schema),
            "tables": schema_table_count,
            "views": schema_view_count,
            "functions": schema_func_count,
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
        "functions_created": total_functions,
        "total_objects": total_tables + total_views + total_functions,
    }
    logger.info(f"Scan complete: {summary}")
    return summary


def _parse_schema_file_path(file_path: str) -> Tuple[str, str, str]:
    """
    Parse a schema library markdown file path into data_source_slug, schema_name, table_name.

    Expected pattern: .../data-sources/{data_source_slug}/schemas/{schema_name}/{schema_name}.{table_name}.md
    Function files use: {schema_name}.fn.{function_name}.md — the "fn." prefix is stripped.
    or Windows: ...\\data-sources\\{data_source_slug}\\schemas\\{schema_name}\\...

    Returns:
        (data_source_slug, schema_name, table_name)
    """
    path = Path(file_path)
    parts = path.parts
    try:
        # Normalize to find "data-sources" in path
        idx_ds = next(i for i, p in enumerate(parts) if p == "data-sources")
        data_source_slug = parts[idx_ds + 1]
        idx_schemas = next(i for i, p in enumerate(parts) if p == "schemas")
        schema_name = parts[idx_schemas + 1]
        stem = path.stem  # e.g. "dbo.ADM_Reports" or "dbo.fn.GetTotal"
        if "." in stem:
            # schema.TableName, schema.ViewName, or schema.fn.FunctionName
            remainder = ".".join(stem.split(".")[1:])
            # Strip "fn." prefix used for function files to get the object name
            if remainder.startswith("fn."):
                remainder = remainder[3:]
            table_name = remainder
        else:
            table_name = stem
        return data_source_slug, schema_name, table_name
    except (StopIteration, IndexError) as e:
        raise ValueError(f"Cannot parse schema file path: {file_path}") from e


def sync_schema_file_from_database(file_path: str) -> str:
    """
    Rebuild a schema library markdown file by loading table and column descriptions
    from the database, then write the file and return the new content.

    Args:
        file_path: Path to the .md file (e.g. skills/data-sources/jcm/schemas/dbo/dbo.TableName.md)

    Returns:
        The new markdown content.

    Raises:
        ValueError: If path cannot be parsed or object not found.
    """
    from app.core.database import get_database_engine
    from app.services.skills_service import get_skills_service

    data_source_slug, schema_name, table_name = _parse_schema_file_path(file_path)

    # Resolve display name for data source (for header)
    data_source_name = data_source_slug
    try:
        skills = get_skills_service()
        sources = skills.load_data_sources_index()
        for s in sources:
            sid = getattr(s, "source_id", None) or _slugify(getattr(s, "name", ""))
            if sid == data_source_slug or (getattr(s, "name", "") or "").lower() == data_source_slug.lower():
                data_source_name = getattr(s, "name", None) or getattr(s, "friendly_name", data_source_slug)
                break
    except Exception:
        pass

    engine = get_database_engine(data_source_slug)
    inspector = inspect(engine)
    tables = inspector.get_table_names(schema=schema_name)
    views = inspector.get_view_names(schema=schema_name)
    if table_name in views:
        obj_type = "view"
    elif table_name in tables:
        obj_type = "table"
    else:
        raise ValueError(f"Object {schema_name}.{table_name} not found in database")

    new_description_block = _build_description_and_columns_block(
        engine, inspector, schema_name, table_name, obj_type
    )

    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"File not found: {file_path}")

    existing_content = path.read_text(encoding="utf-8")
    merged = _merge_description_section(existing_content, new_description_block)
    # If file had no "## Description" section, merge returns unchanged; then do full replace
    if merged == existing_content:
        content, _ = _build_object_markdown(
            engine, inspector, schema_name, table_name, obj_type, data_source_name
        )
        path.write_text(content, encoding="utf-8")
        content_to_return = content
    else:
        path.write_text(merged, encoding="utf-8")
        content_to_return = merged

    # Clear skills cache so next read sees the new content
    try:
        skills = get_skills_service()
        skills._data_sources_cache = None
        skills._data_groups_cache = None
    except Exception:
        pass

    return content_to_return


def _build_description_and_columns_block(
    engine, inspector, schema_name: str, obj_name: str, obj_type: str
) -> str:
    """
    Build only the table description and columns block (markdown_body) from the database.
    Used when syncing to update just that section and preserve other manual sections.
    """
    columns = inspector.get_columns(obj_name, schema=schema_name)
    fk_map = get_foreign_key_map(inspector, obj_name, schema_name) if obj_type == "table" else {}
    pk_columns = get_primary_key_columns(inspector, obj_name, schema_name) if obj_type == "table" else []
    db_description = get_table_description(engine, obj_name, schema_name, obj_type)
    if not db_description:
        db_description = f"Stores {obj_name} data."
    return build_table_markdown_description(
        schema_name=schema_name,
        table_name=obj_name,
        table_description=db_description,
        columns=columns,
        fk_map=fk_map,
        pk_columns=pk_columns,
        table_type=obj_type,
    )


def _merge_description_section(existing_content: str, new_description_block: str) -> str:
    """
    Replace only the "## Description" section (table description + columns) in existing content.
    Everything before (header, metadata) and after (other manual sections) is preserved.
    If "## Description" is not found, returns existing_content unchanged (caller may fall back to full replace).
    """
    # Find start of ## Description (allow optional leading newline / at start of file)
    desc_marker = "## Description"
    start = existing_content.find(desc_marker)
    if start == -1:
        return existing_content
    # End of section: next "\n## " (start of another section) or end of file
    after_desc = start + len(desc_marker)
    next_section = existing_content.find("\n## ", after_desc)
    if next_section == -1:
        end = len(existing_content)
        content_after = ""
    else:
        end = next_section
        content_after = existing_content[end:].lstrip("\n")
    content_before = existing_content[:start]
    new_section = "## Description\n\n" + new_description_block.rstrip()
    if content_after:
        return content_before + new_section + "\n\n" + content_after
    return content_before + new_section


def _build_object_markdown(
    engine, inspector, schema_name: str, obj_name: str,
    obj_type: str, data_source_name: str
) -> Tuple[str, Dict]:
    """
    Build the full markdown file content and metadata dict for a single DB object.
    """
    markdown_body = _build_description_and_columns_block(
        engine, inspector, schema_name, obj_name, obj_type
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
    db_description = get_table_description(engine, obj_name, schema_name, obj_type) or f"Stores {obj_name} data."
    keywords = _extract_keywords(obj_name, db_description)
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
            fname = obj.get("file_name", f"{s}.{n}.md")
            object_links.append(f"- **[{s}.{n}](../schemas/{s}/{fname})** - {t}")

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
