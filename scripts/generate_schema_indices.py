"""
Script to generate schema index files for better discoverability
Creates:
1. .schema-index.json in each data source folder
2. .object-index.json in each schema folder
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Any


def extract_metadata_from_md(file_path: Path) -> Dict[str, Any]:
    """Extract metadata from a schema markdown file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract schema name
        schema_match = re.search(r'\*\*Schema:\*\*\s+(\w+)', content)
        schema_name = schema_match.group(1) if schema_match else 'unknown'
        
        # Extract object type (Table or View)
        type_match = re.search(r'\*\*Type:\*\*\s+(\w+)', content)
        object_type = type_match.group(1) if type_match else 'unknown'
        
        # Extract object name from title
        name_match = re.search(r'#\s+(?:Table|View):\s+\[(\w+)\]\.\[([^\]]+)\]', content)
        if name_match:
            schema_from_title = name_match.group(1)
            object_name = name_match.group(2)
        else:
            schema_from_title = schema_name
            object_name = file_path.stem.split('.')[-1] if '.' in file_path.stem else file_path.stem
        
        # Extract description (the part after the "Table:" or "View:" heading)
        desc_match = re.search(r'#\s+\*\*(?:Table|View):\*\*\s+`\[[^\]]+\]\.\[[^\]]+\]`\s*\n>\s+([^\n]+)', content)
        description = desc_match.group(1).strip() if desc_match else ''
        
        # Generate keywords from description and object name
        keywords = []
        if description:
            # Extract meaningful words from description (excluding common words)
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            words = re.findall(r'\b\w+\b', description.lower())
            keywords = [w for w in words if len(w) > 3 and w not in stop_words][:5]
        
        # Add object name parts as keywords
        object_parts = re.findall(r'[A-Z][a-z]+|[a-z]+', object_name)
        keywords.extend([p.lower() for p in object_parts if len(p) > 2])
        keywords = list(dict.fromkeys(keywords))[:8]  # Deduplicate and limit
        
        return {
            'schema_name': schema_name,
            'object_type': object_type,
            'object_name': object_name,
            'description': description,
            'keywords': keywords,
            'file_name': file_path.name
        }
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None


def generate_object_index(schema_path: Path) -> Dict[str, Any]:
    """Generate .object-index.json for a schema folder"""
    objects = []
    
    # Get all .md files in the schema folder
    md_files = sorted(schema_path.glob('*.md'))
    
    for md_file in md_files:
        metadata = extract_metadata_from_md(md_file)
        if metadata:
            objects.append({
                'object_type': metadata['object_type'],
                'schema_name': metadata['schema_name'],
                'object_name': metadata['object_name'],
                'description': metadata['description'],
                'keywords': metadata['keywords'],
                'file_name': metadata['file_name']
            })
    
    return {
        'schema': schema_path.name,
        'total_objects': len(objects),
        'tables': len([o for o in objects if o['object_type'] == 'Table']),
        'views': len([o for o in objects if o['object_type'] == 'View']),
        'objects': objects
    }


def generate_schema_index(data_source_path: Path) -> Dict[str, Any]:
    """Generate .schema-index.json for a data source folder"""
    schemas_path = data_source_path / 'schemas'
    if not schemas_path.exists():
        return None
    
    schemas = []
    
    # Get all schema folders
    for schema_folder in sorted(schemas_path.iterdir()):
        if not schema_folder.is_dir():
            continue
        
        # Count objects
        md_files = list(schema_folder.glob('*.md'))
        table_count = 0
        view_count = 0
        
        for md_file in md_files:
            metadata = extract_metadata_from_md(md_file)
            if metadata:
                if metadata['object_type'] == 'Table':
                    table_count += 1
                elif metadata['object_type'] == 'View':
                    view_count += 1
        
        schemas.append({
            'schema_name': schema_folder.name,
            'description': f'Contains {table_count} tables and {view_count} views',
            'object_index_file': f'schemas/{schema_folder.name}/.object-index.json',
            'total_objects': len(md_files),
            'tables': table_count,
            'views': view_count
        })
    
    return {
        'data_source': data_source_path.name,
        'total_schemas': len(schemas),
        'schemas': schemas
    }


def main():
    """Main function to generate all index files"""
    # Get the skills/data-sources directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    data_sources_dir = project_root / 'skills' / 'data-sources'
    
    if not data_sources_dir.exists():
        print(f"Error: Data sources directory not found: {data_sources_dir}")
        return
    
    # Process each data source
    for data_source_folder in data_sources_dir.iterdir():
        if not data_source_folder.is_dir() or data_source_folder.name.startswith('_'):
            continue
        
        print(f"\n{'='*60}")
        print(f"Processing data source: {data_source_folder.name}")
        print(f"{'='*60}")
        
        # Generate schema index for the data source
        schema_index = generate_schema_index(data_source_folder)
        if schema_index:
            schema_index_file = data_source_folder / '.schema-index.json'
            with open(schema_index_file, 'w', encoding='utf-8') as f:
                json.dump(schema_index, f, indent=2, ensure_ascii=False)
            print(f"✓ Created {schema_index_file}")
            print(f"  - {schema_index['total_schemas']} schemas indexed")
        
        # Generate object index for each schema
        schemas_path = data_source_folder / 'schemas'
        if schemas_path.exists():
            for schema_folder in schemas_path.iterdir():
                if not schema_folder.is_dir():
                    continue
                
                object_index = generate_object_index(schema_folder)
                if object_index:
                    object_index_file = schema_folder / '.object-index.json'
                    with open(object_index_file, 'w', encoding='utf-8') as f:
                        json.dump(object_index, f, indent=2, ensure_ascii=False)
                    print(f"✓ Created {object_index_file}")
                    print(f"  - {object_index['total_objects']} objects indexed")
                    print(f"    ({object_index['tables']} tables, {object_index['views']} views)")
    
    print(f"\n{'='*60}")
    print("✓ All index files generated successfully!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
