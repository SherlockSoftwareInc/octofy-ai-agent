"""
Skills Admin Service - Handles CRUD operations for skills files
"""

import os
import re
import uuid
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from app.models.schemas import DataSource, DataGroup, TableSchema


SKILLS_BASE_PATH = Path("skills/data-sources")


def _slugify(name: str) -> str:
    """Convert name to filesystem-safe slug"""
    return re.sub(r'[^\w\s-]', '', name.lower()).replace(' ', '-')


def _ensure_skills_directory():
    """Ensure skills base directory exists"""
    SKILLS_BASE_PATH.mkdir(parents=True, exist_ok=True)


def _read_data_groups_file(ds_dir: Path) -> List[Tuple[str, str]]:
    """
    Read .data-groups file and return list of (name, filename) tuples
    
    Args:
        ds_dir: Data source directory
        
    Returns:
        List of (group_name, group_filename) tuples
    """
    data_groups_file = ds_dir / ".data-groups"
    
    if not data_groups_file.exists():
        return []
    
    groups = []
    content = data_groups_file.read_text(encoding='utf-8')
    
    for line in content.strip().split('\n'):
        if not line.strip():
            continue
        
        # Parse format: "Group Name|_filename-group.md"
        if '|' in line:
            name, filename = line.split('|', 1)
            groups.append((name.strip(), filename.strip()))
    
    return groups


def _append_to_data_groups_file(ds_dir: Path, group_name: str, group_filename: str):
    """
    Append a new entry to .data-groups file
    
    Args:
        ds_dir: Data source directory
        group_name: Display name of the group
        group_filename: Filename of the group (e.g., "_contacts-group.md")
    """
    data_groups_file = ds_dir / ".data-groups"
    
    # Read existing content
    existing_groups = _read_data_groups_file(ds_dir)
    
    # Check if already exists
    for _, filename in existing_groups:
        if filename == group_filename:
            # Already exists, don't add duplicate
            return
    
    # Append new entry
    entry = f"{group_name}|{group_filename}\n"
    
    if data_groups_file.exists():
        # Append to existing file
        with open(data_groups_file, 'a', encoding='utf-8') as f:
            f.write(entry)
    else:
        # Create new file
        data_groups_file.write_text(entry, encoding='utf-8')


def _remove_from_data_groups_file(ds_dir: Path, group_filename: str):
    """
    Remove an entry from .data-groups file
    
    Args:
        ds_dir: Data source directory
        group_filename: Filename of the group to remove
    """
    data_groups_file = ds_dir / ".data-groups"
    
    if not data_groups_file.exists():
        return
    
    # Read all groups
    existing_groups = _read_data_groups_file(ds_dir)
    
    # Filter out the one to remove
    updated_groups = [(name, filename) for name, filename in existing_groups 
                      if filename != group_filename]
    
    # Write back
    if updated_groups:
        content = '\n'.join([f"{name}|{filename}" for name, filename in updated_groups]) + '\n'
        data_groups_file.write_text(content, encoding='utf-8')
    else:
        # If empty, write empty file
        data_groups_file.write_text('', encoding='utf-8')


def create_data_source(data: Dict) -> Dict:
    """
    Create a new data source
    
    Args:
        data: Dictionary with name, type, description, keywords, status,
              and optionally server, database for SQL Server sources
        
    Returns:
        Dictionary with created data source info
    """
    _ensure_skills_directory()
    
    name = data.get('name', '').strip()
    if not name:
        raise ValueError("Data source name is required")
    
    ds_type = data.get('type', 'SQL Server')
    description = data.get('description', '')
    keywords = data.get('keywords', [])
    status = data.get('status', 'Active')
    server = data.get('server', '').strip()
    database = data.get('database', '').strip()
    
    # Create directory
    slug = _slugify(name)
    ds_dir = SKILLS_BASE_PATH / slug
    if ds_dir.exists():
        raise ValueError(f"Data source '{name}' already exists")
    
    ds_dir.mkdir(parents=True, exist_ok=True)
    (ds_dir / "data-groups").mkdir(exist_ok=True)
    (ds_dir / "schemas").mkdir(exist_ok=True)
    
    # Create _data-source.md
    ds_file = ds_dir / "_data-source.md"
    keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
    source_id = str(uuid.uuid4())
    
    # Build connection fields if provided
    connection_lines = ""
    if server:
        connection_lines += f"**Server:** {server}\n"
    if database:
        connection_lines += f"**Database:** {database}\n"
    
    description_text = description if description else f"Data source for {name}."
    
    content = f"""---
source_id: {source_id}
---

# {name}

**Type:** {ds_type}  
{connection_lines}
**Friendly Name:** {name}  
**Keywords:** {keywords_str}

## Description

{description_text}

## Data Coverage

- **Time Range:** Unknown (requires manual update)
- **Update Frequency:** Unknown (requires manual update)

## Schema Notes

- Specific time ranges
- Update frequency
- Cross-schema references
- Access restrictions

## Connection Method

```python
# SQL Server connection via pyodbc
# See app settings for connection string
```

## Physical Schemas

All table schemas are stored in the `schemas/` directory, organized by database schema:
"""
    
    ds_file.write_text(content, encoding='utf-8')
    
    # Create empty .data-groups file
    data_groups_file = ds_dir / ".data-groups"
    data_groups_file.write_text('', encoding='utf-8')
    
    # Update _index.md
    _update_index_with_data_source(name, ds_type, status, description, keywords_str, f"{slug}/_data-source.md", source_id)
    
    return {
        "name": name,
        "source_id": source_id,
        "type": ds_type,
        "status": status,
        "description": description,
        "keywords": keywords,
        "file_path": str(ds_file)
    }


def update_data_source(data_source_name: str, data: Dict) -> Dict:
    """
    Update an existing data source
    
    Args:
        data_source_name: Name of the data source to update
        data: Dictionary with updated fields
        
    Returns:
        Dictionary with updated data source info
    """
    # Find the data source directory
    slug = _slugify(data_source_name)
    ds_dir = SKILLS_BASE_PATH / slug
    ds_file = ds_dir / "_data-source.md"
    
    if not ds_file.exists():
        raise ValueError(f"Data source '{data_source_name}' not found")
    
    # Read current content
    content = ds_file.read_text(encoding='utf-8')
    
    # Update fields
    new_name = data.get('name', data_source_name).strip()
    ds_type = data.get('type')
    description = data.get('description')
    keywords = data.get('keywords')
    status = data.get('status')
    
    # Update content
    if new_name != data_source_name:
        content = re.sub(r'^# .+$', f'# {new_name}', content, count=1, flags=re.MULTILINE)
    
    if ds_type:
        content = re.sub(r'\*\*Type:\*\* .+', f'**Type:** {ds_type}', content)
    
    if status:
        content = re.sub(r'\*\*Status:\*\* .+', f'**Status:** {status}', content)
    
    if description is not None:
        content = re.sub(r'\*\*Description:\*\* .+', f'**Description:** {description}', content)
    
    if keywords is not None:
        keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
        content = re.sub(r'\*\*Keywords:\*\* .+', f'**Keywords:** {keywords_str}', content)
    
    ds_file.write_text(content, encoding='utf-8')
    
    # Update _index.md
    _update_index_for_existing_data_source(data_source_name, new_name, ds_type, status, description, keywords)
    
    return {
        "name": new_name,
        "file_path": str(ds_file)
    }


def delete_data_source(data_source_name: str):
    """
    Delete a data source and all its contents
    
    Args:
        data_source_name: Name of the data source to delete
    """
    slug = _slugify(data_source_name)
    ds_dir = SKILLS_BASE_PATH / slug
    
    if not ds_dir.exists():
        raise ValueError(f"Data source '{data_source_name}' not found")
    
    # Delete directory recursively
    import shutil
    shutil.rmtree(ds_dir)
    
    # Remove from _index.md
    _remove_from_index(data_source_name)


def create_data_group(data: Dict) -> Dict:
    """
    Create a new data group
    
    Args:
        data: Dictionary with name, data_source, description, keywords, category, tables
        
    Returns:
        Dictionary with created data group info
    """
    name = data.get('name', '').strip()
    data_source = data.get('data_source', '').strip()
    description = data.get('description', '')
    keywords = data.get('keywords', [])
    category = data.get('category', 'User-defined')
    tables = data.get('tables', [])
    
    if not name or not data_source:
        raise ValueError("Data group name and data_source are required")
    
    # Find data source directory
    slug = _slugify(data_source)
    ds_dir = SKILLS_BASE_PATH / slug
    if not ds_dir.exists():
        raise ValueError(f"Data source '{data_source}' not found")
    
    groups_dir = ds_dir / "data-groups"
    groups_dir.mkdir(exist_ok=True)
    
    # Create group file
    group_slug = _slugify(name)
    group_file = groups_dir / f"_{group_slug}-group.md"
    
    if group_file.exists():
        raise ValueError(f"Data group '{name}' already exists in '{data_source}'")
    
    keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
    
    content = f"""# {name}

**Data Source:** {data_source}
**Category:** {category}
**Keywords:** {keywords_str}

## Description

{description}

## Data Objects

"""
    
    # Add table references
    if tables:
        for table_path in tables:
            # Extract table name from path
            table_name = Path(table_path).stem
            rel_path = os.path.relpath(table_path, group_file.parent)
            content += f"- **[{table_name}]({rel_path})** - Table\n"
    else:
        content += "No tables assigned yet.\n"
    
    group_file.write_text(content, encoding='utf-8')
    
    # Add entry to .data-groups file
    group_filename = group_file.name
    _append_to_data_groups_file(ds_dir, name, group_filename)
    
    return {
        "name": name,
        "data_source": data_source,
        "description": description,
        "keywords": keywords,
        "category": category,
        "tables": tables,
        "file_path": str(group_file)
    }


def update_data_group(data: Dict) -> Dict:
    """
    Update an existing data group
    
    Args:
        data: Dictionary with file_path and updated fields
        
    Returns:
        Dictionary with updated data group info
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("file_path is required for updating data group")
    
    group_file = Path(file_path)
    if not group_file.exists():
        raise ValueError(f"Data group file not found: {file_path}")
    
    content = group_file.read_text(encoding='utf-8')
    
    # Update fields
    name = data.get('name')
    data_source = data.get('data_source')
    description = data.get('description')
    keywords = data.get('keywords')
    category = data.get('category')
    tables = data.get('tables')
    
    if name:
        content = re.sub(r'^# .+$', f'# {name}', content, count=1, flags=re.MULTILINE)
    
    if data_source:
        content = re.sub(r'\*\*Data Source:\*\* .+', f'**Data Source:** {data_source}', content)
    
    if category:
        content = re.sub(r'\*\*Category:\*\* .+', f'**Category:** {category}', content)
    
    if keywords is not None:
        keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
        content = re.sub(r'\*\*Keywords:\*\* .+', f'**Keywords:** {keywords_str}', content)
    
    if description is not None:
        # Replace description section
        content = re.sub(
            r'(## Description\s*\n\n).*?(\n\n##)',
            f'\\1{description}\\2',
            content,
            flags=re.DOTALL
        )
    
    if tables is not None:
        # Rebuild tables section
        tables_section = "\n## Data Objects\n\n"
        if tables:
            for table_path in tables:
                table_name = Path(table_path).stem
                rel_path = os.path.relpath(table_path, group_file.parent)
                tables_section += f"- **[{table_name}]({rel_path})** - Table\n"
        else:
            tables_section += "No tables assigned yet.\n"
        
        content = re.sub(
            r'## Data Objects\s*\n.*',
            tables_section,
            content,
            flags=re.DOTALL
        )
    
    group_file.write_text(content, encoding='utf-8')
    
    return {
        "file_path": str(group_file),
        "updated": True
    }


def delete_data_group(file_path: str):
    """
    Delete a data group file
    
    Args:
        file_path: Path to the data group file
    """
    group_file = Path(file_path)
    if not group_file.exists():
        raise ValueError(f"Data group file not found: {file_path}")
    
    # Extract filename and find data source directory
    group_filename = group_file.name
    ds_dir = group_file.parent.parent  # Go up from data-groups to data source dir
    
    # Remove from .data-groups file
    _remove_from_data_groups_file(ds_dir, group_filename)
    
    # Delete the file
    group_file.unlink()


def create_table_schema(data: Dict) -> Dict:
    """
    Create a new table schema file (data object)
    
    Args:
        data: Dictionary with data_source, schema_name, table_name, description, columns
        
    Returns:
        Dictionary with created table info
    """
    data_source = data.get('data_source', '').strip()
    schema_name = data.get('schema_name', 'dbo').strip()
    table_name = data.get('table_name', '').strip()
    description = data.get('description', '')
    columns = data.get('columns', [])
    table_type = data.get('table_type', 'Table')
    record_count = data.get('record_count', 'Unknown')
    
    if not data_source or not table_name:
        raise ValueError("data_source and table_name are required")
    
    # Find data source directory
    ds_slug = _slugify(data_source)
    ds_dir = SKILLS_BASE_PATH / ds_slug
    if not ds_dir.exists():
        raise ValueError(f"Data source '{data_source}' not found")
    
    # Create schema directory if needed
    schemas_dir = ds_dir / "schemas" / schema_name
    schemas_dir.mkdir(parents=True, exist_ok=True)
    
    # Create table file
    table_file = schemas_dir / f"{schema_name}.{table_name}.md"
    
    if table_file.exists():
        raise ValueError(f"Table '{schema_name}.{table_name}' already exists in '{data_source}'")
    
    # Build columns section
    columns_section = ""
    if columns:
        for i, col in enumerate(columns, 1):
            col_name = col.get('name', '')
            col_type = col.get('type', '')
            col_desc = col.get('description', '')
            columns_section += f"""
### {i}. {col_name}
**Type:** `{col_type}`
**Description:** {col_desc}
"""
    else:
        columns_section = "\nNo columns defined yet.\n"
    
    # Create content
    content = f"""# Table: [{schema_name}].[{table_name}]

**Data Source:** {data_source}
**Schema:** {schema_name}
**Type:** {table_type}
**Record Count:** {record_count}

## Description

{description}

## Columns
{columns_section}

## Common Queries

(Add common query patterns here)

## Related Tables

(List related tables and their relationships here)
"""
    
    table_file.write_text(content, encoding='utf-8')
    
    return {
        "data_source": data_source,
        "schema_name": schema_name,
        "table_name": table_name,
        "description": description,
        "file_path": str(table_file)
    }


def update_table_schema(data: Dict) -> Dict:
    """
    Update an existing table schema
    
    Args:
        data: Dictionary with file_path and updated fields (description, columns)
        
    Returns:
        Dictionary with updated table info
    """
    file_path = data.get('file_path')
    if not file_path:
        raise ValueError("file_path is required for updating table schema")
    
    table_file = Path(file_path)
    if not table_file.exists():
        raise ValueError(f"Table file not found: {file_path}")
    
    content = table_file.read_text(encoding='utf-8')
    
    # Update description if provided
    description = data.get('description')
    if description is not None:
        # Find the description section (after the first heading and metadata, before ## Columns)
        content = re.sub(
            r'(^#[^#].*?\n\n(?:\*\*.*?\n)*\n).*?(\n## Columns)',
            f'\\1{description}\\2',
            content,
            flags=re.DOTALL | re.MULTILINE
        )
    
    table_file.write_text(content, encoding='utf-8')
    
    return {
        "file_path": str(table_file),
        "updated": True
    }


def delete_table_schema(file_path: str):
    """
    Delete a table schema file
    
    Args:
        file_path: Path to the table schema file
    """
    table_file = Path(file_path)
    if not table_file.exists():
        raise ValueError(f"Table file not found: {file_path}")
    
    table_file.unlink()


def _update_index_with_data_source(name: str, ds_type: str, status: str, description: str, keywords_str: str, skill_file: str, source_id: str):
    """Add a new data source to _index.md"""
    index_file = SKILLS_BASE_PATH / "_index.md"
    
    if not index_file.exists():
        # Create new index file
        content = f"""# Data Sources Index

This file catalogs all available data sources for the skills-based discovery system.

### {name}
**Type:** {ds_type}
**Source ID:** {source_id}
**Status:** {status}
**Description:** {description}
**Keywords:** {keywords_str}
**Skill File:** [{skill_file}]({skill_file})

"""
    else:
        content = index_file.read_text(encoding='utf-8')
        
        # Append new data source
        new_section = f"""
### {name}
**Type:** {ds_type}
**Source ID:** {source_id}
**Status:** {status}
**Description:** {description}
**Keywords:** {keywords_str}
**Skill File:** [{skill_file}]({skill_file})
"""
        content += new_section
    
    index_file.write_text(content, encoding='utf-8')


def _update_index_for_existing_data_source(old_name: str, new_name: str, ds_type: Optional[str], status: Optional[str], description: Optional[str], keywords):
    """Update an existing data source in _index.md"""
    index_file = SKILLS_BASE_PATH / "_index.md"
    if not index_file.exists():
        return
    
    content = index_file.read_text(encoding='utf-8')
    
    # Find and update the section
    pattern = f'### {re.escape(old_name)}.*?(?=\n###|\Z)'
    
    def replace_section(match):
        section = match.group(0)
        
        if new_name != old_name:
            section = re.sub(r'^### .+$', f'### {new_name}', section, flags=re.MULTILINE)
        
        if ds_type:
            section = re.sub(r'\*\*Type:\*\* .+', f'**Type:** {ds_type}', section)
        
        if status:
            section = re.sub(r'\*\*Status:\*\* .+', f'**Status:** {status}', section)
        
        if description is not None:
            section = re.sub(r'\*\*Description:\*\* .+', f'**Description:** {description}', section)
        
        if keywords is not None:
            keywords_str = ', '.join(keywords) if isinstance(keywords, list) else keywords
            section = re.sub(r'\*\*Keywords:\*\* .+', f'**Keywords:** {keywords_str}', section)
        
        return section
    
    content = re.sub(pattern, replace_section, content, flags=re.DOTALL)
    index_file.write_text(content, encoding='utf-8')


def _remove_from_index(data_source_name: str):
    """Remove a data source from _index.md"""
    index_file = SKILLS_BASE_PATH / "_index.md"
    if not index_file.exists():
        return
    
    content = index_file.read_text(encoding='utf-8')
    
    # Remove the section
    pattern = f'### {re.escape(data_source_name)}.*?(?=\n###|\Z)'
    content = re.sub(pattern, '', content, flags=re.DOTALL)
    
    index_file.write_text(content, encoding='utf-8')
