"""
Migration Script: Convert Milvus schema_index to Skills Files

This script reads all table schemas from Milvus schema_index collection
and generates the skills directory structure with markdown files.

Usage:
    python scripts/migrate_milvus_to_skills.py [--output-dir skills/data-sources] [--dry-run]
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Set
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.vector_store import get_vector_store
from app.models.schemas import TableSchema
from app.core.config import settings


def normalize_name(name: str) -> str:
    """Convert name to valid directory/filename"""
    # Replace special characters with underscores
    return name.replace(' ', '-').replace('[', '').replace(']', '').replace('.', '_').lower()


def group_tables_by_schema(tables: List[TableSchema]) -> Dict[str, List[TableSchema]]:
    """Group tables by schema name"""
    groups = defaultdict(list)
    for table in tables:
        groups[table.schema_name].append(table)
    return dict(groups)


def infer_data_groups(tables: List[TableSchema]) -> Dict[str, List[TableSchema]]:
    """
    Infer logical data groups from table names and descriptions
    
    Simple heuristic: group by common prefix (e.g., ECG_, Customer, Order)
    """
    groups = defaultdict(list)
    
    for table in tables:
        # Try to find common prefix
        table_name = table.table_name
        
        # Common patterns
        if '_' in table_name:
            # Use prefix before underscore (e.g., ECG_PreProcedure -> ECG)
            prefix = table_name.split('_')[0]
            groups[prefix].append(table)
        elif table_name.startswith('vw'):
            # Views group
            groups['views'].append(table)
        else:
            # Default: use table name as its own group
            groups[table_name].append(table)
    
    return dict(groups)


def extract_keywords_from_description(description: str) -> List[str]:
    """Extract potential keywords from table description"""
    if not description:
        return []
    
    # Simple keyword extraction: look for nouns and important terms
    # This is basic - manual enhancement recommended
    import re
    
    # Extract capitalized words and common technical terms
    words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', description)
    
    # Clean and deduplicate
    keywords = list(set([w.lower() for w in words if len(w) > 3]))
    
    return keywords[:10]  # Limit to top 10


def generate_index_file(data_sources: List[Dict], output_dir: Path):
    """Generate _index.md file"""
    content = """# Data Sources Catalog

Last updated: {date}

## Available Data Sources

""".format(date=Path(__file__).stat().st_mtime)
    
    for ds in data_sources:
        content += f"""### {ds['name']}
**Type:** {ds['type']}  
**Status:** {ds['status']}  
**Description:** {ds['description']}  
**Keywords:** {', '.join(ds['keywords'])}  
**Skill File:** [{ds['folder']}/_data-source.md]({ds['folder']}/_data-source.md)

"""
    
    index_path = output_dir / "_index.md"
    index_path.write_text(content, encoding='utf-8')
    print(f"[SUCCESS] Created {index_path}")


def generate_data_source_file(ds_info: Dict, output_dir: Path):
    """Generate _data-source.md file for a data source"""
    ds_dir = output_dir / ds_info['folder']
    ds_dir.mkdir(parents=True, exist_ok=True)
    
    # Create data-groups and schemas subdirectories
    (ds_dir / "data-groups").mkdir(exist_ok=True)
    (ds_dir / "schemas").mkdir(exist_ok=True)
    
    content = f"""# {ds_info['name']}

**Type:** {ds_info['type']}  
**Server:** Unknown (see settings)  
**Database:** Unknown (see settings)  
**Status:** {ds_info['status']}  
**Maintainer:** Database Administrator  
**Last Sync:** Auto-generated from Milvus

## Description

{ds_info['description']}

## Data Coverage

- **Time Range:** Unknown (requires manual update)
- **Update Frequency:** Unknown (requires manual update)

## Schema Notes

This data source was auto-generated from the Milvus schema_index collection.
Please manually enhance with:
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
    
    # List schema directories
    for schema_name in ds_info['schema_names']:
        content += f"- **schemas/{schema_name}/** - {schema_name.capitalize()} schema tables\n"
    
    ds_file = ds_dir / "_data-source.md"
    ds_file.write_text(content, encoding='utf-8')
    print(f"[SUCCESS] Created {ds_file}")
    
    # Create .data-groups file
    data_groups_file = ds_dir / ".data-groups"
    data_groups_content = ""
    
    for group_name in ds_info['groups']:
        group_file = f"_{normalize_name(group_name)}-group.md"
        # The group file will be created later, so we construct the title now
        # Format: "GroupName Data Group" (consistent with the group file title)
        group_title = f"{group_name} Data Group"
        data_groups_content += f"{group_title}|{group_file}\n"
    
    data_groups_file.write_text(data_groups_content, encoding='utf-8')
    print(f"[SUCCESS] Created {data_groups_file} with {len(ds_info['groups'])} groups")


def generate_data_group_file(group_info: Dict, ds_folder: str, output_dir: Path):
    """Generate _data-group.md file for a data group"""
    group_dir = output_dir / ds_folder / "data-groups"
    group_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract keywords from descriptions
    all_keywords = set()
    for table in group_info['tables']:
        keywords = extract_keywords_from_description(table.description or "")
        all_keywords.update(keywords)
    
    # Add group name as keyword
    all_keywords.add(group_info['name'].lower())
    
    group_file = f"_{normalize_name(group_info['name'])}-group.md"
    
    content = f"""# {group_info['name']} Data Group

**Data Source:** {group_info['data_source']}  
**Category:** Auto-generated  
**Keywords:** {', '.join(sorted(all_keywords))}

## Description

This data group was auto-generated from Milvus schema_index.
Contains {len(group_info['tables'])} table(s).

## Data Objects

"""
    
    # Group tables by schema for better organization
    tables_by_schema = defaultdict(list)
    for table in group_info['tables']:
        tables_by_schema[table.schema_name].append(table)
    
    # List all tables in this group, organized by schema
    for schema_name, tables in sorted(tables_by_schema.items()):
        content += f"""### {schema_name.capitalize()} Schema

"""
        for table in tables:
            # Path to schema file: ../schemas/{schema_name}/{schema}.{table}.md
            schema_file = f"../schemas/{schema_name}/{table.schema_name}.{table.table_name}.md"
            record_count = "Unknown"
            content += f"""- **[{table.schema_name}.{table.table_name}]({schema_file})** - {table.table_type.capitalize()} ({record_count} records)
"""
        content += "\n"
    
    file_path = group_dir / group_file
    file_path.write_text(content, encoding='utf-8')
    print(f"[SUCCESS] Created {file_path}")


def generate_table_file(table: TableSchema, ds_folder: str, output_dir: Path):
    """Generate individual table schema .md file in schemas/{schema_name}/ directory"""
    # Create schema-specific directory: {ds_folder}/schemas/{schema_name}/
    schema_dir = output_dir / ds_folder / "schemas" / table.schema_name
    schema_dir.mkdir(parents=True, exist_ok=True)
    
    content = f"""# Table: [{table.schema_name}].[{table.table_name}]

**Data Source:** Auto-generated  
**Schema:** {table.schema_name}  
**Type:** {table.table_type.capitalize() if table.table_type else 'Table'}

## Description

{table.description or 'No description available. Please add manually.'}
"""
    
    table_file = schema_dir / f"{table.schema_name}.{table.table_name}.md"
    table_file.write_text(content, encoding='utf-8')
    print(f"  [SUCCESS] Created table file: {table.schema_name}.{table.table_name}")


def migrate_milvus_to_skills(output_dir: str, dry_run: bool = False):
    """
    Main migration function
    
    Args:
        output_dir: Output directory for skills files
        dry_run: If True, only print what would be done without creating files
    """
    print("=" * 60)
    print("Milvus to Skills Migration Script")
    print("=" * 60)
    
    output_path = Path(output_dir)
    
    if dry_run:
        print("\n[DRY RUN] MODE - No files will be created\n")
    else:
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"\n[OUTPUT] Directory: {output_path.absolute()}\n")
    
    # Connect to Milvus and fetch all schemas
    print("[INFO] Connecting to Milvus...")
    try:
        vector_store = get_vector_store()
        all_tables = vector_store.get_all_schemas()
        print(f"[SUCCESS] Found {len(all_tables)} tables in schema_index")
    except Exception as e:
        print(f"[ERROR] Error connecting to Milvus: {e}")
        return
    
    if not all_tables:
        print("[WARNING] No tables found in Milvus schema_index. Nothing to migrate.")
        return
    
    # Group tables by schema (data source)
    print("\n[INFO] Analyzing table structure...")
    tables_by_schema = group_tables_by_schema(all_tables)
    print(f"[SUCCESS] Found {len(tables_by_schema)} schema(s)")
    
    # Build data source info
    data_sources = []
    for schema_name, tables in tables_by_schema.items():
        # Infer data groups within this schema
        data_groups = infer_data_groups(tables)
        
        ds_folder = normalize_name(schema_name + "-database")
        
        # Determine database type from settings
        db_type = "SQL Server"  # Default
        
        # Get unique schema names for this data source
        schema_names = set([t.schema_name for t in tables])
        
        ds_info = {
            'name': f"{schema_name.capitalize()} Database",
            'type': db_type,
            'status': 'Active',
            'description': f"Database schema: {schema_name}. Contains {len(tables)} tables. Auto-generated from Milvus.",
            'keywords': [schema_name.lower(), 'database', 'sql'],
            'folder': ds_folder,
            'groups': list(data_groups.keys()),
            'schema_name': schema_name,
            'schema_names': sorted(schema_names)
        }
        
        data_sources.append(ds_info)
        
        print(f"\n  [DATA SOURCE] {ds_info['name']}")
        print(f"     Groups: {len(data_groups)}, Tables: {len(tables)}")
        
        if dry_run:
            for group_name, group_tables in data_groups.items():
                print(f"       - {group_name}: {len(group_tables)} tables")
            continue
        
        # Generate files
        generate_data_source_file(ds_info, output_path)
        
        for group_name, group_tables in data_groups.items():
            group_info = {
                'name': group_name,
                'data_source': ds_info['name'],
                'tables': group_tables
            }
            
            generate_data_group_file(group_info, ds_folder, output_path)
        
        # Generate individual table files (organized by schema in schemas/ directory)
        for table in tables:
            generate_table_file(table, ds_folder, output_path)
    
    # Generate top-level index
    if not dry_run:
        print("\n[INFO] Generating top-level index...")
        generate_index_file(data_sources, output_path)
    
    print("\n" + "=" * 60)
    print("[SUCCESS] Migration Complete!")
    print("=" * 60)
    
    if not dry_run:
        print(f"\n[OUTPUT] Skills directory created at: {output_path.absolute()}")
        print("\n[WARNING] IMPORTANT: Manual enhancement recommended:")
        print("   1. Add meaningful keywords to data groups")
        print("   2. Add schema migration notes")
        print("   3. Document common use cases")
        print("   4. Add time ranges and update frequencies")
        print("   5. Review and improve table descriptions")
    else:
        print("\n[INFO] Run without --dry-run to create actual files")


def main():
    parser = argparse.ArgumentParser(description='Migrate Milvus schema_index to Skills files')
    parser.add_argument('--output-dir', default='skills/data-sources',
                       help='Output directory for skills files (default: skills/data-sources)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Print what would be done without creating files')
    
    args = parser.parse_args()
    
    migrate_milvus_to_skills(args.output_dir, args.dry_run)


if __name__ == '__main__':
    main()
