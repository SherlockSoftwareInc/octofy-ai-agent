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
from typing import Dict, List, Any, Optional, Tuple


def extract_schema_metadata_from_md(schema_folder: Path) -> Tuple[Optional[str], List[str]]:
    """
    Extract purpose/domain and keywords from _schema.md in a schema folder.
    Returns (description, keywords). If file is missing or empty, returns (None, []).
    """
    schema_md = schema_folder / '_schema.md'
    if not schema_md.exists():
        return None, []

    try:
        content = schema_md.read_text(encoding='utf-8')
        description = None
        keywords: List[str] = []

        # Purpose or Domain section: first paragraph after the heading
        for section_name in ('## Purpose', '## Domain'):
            match = re.search(
                rf'{re.escape(section_name)}\s*\n+(.+?)(?=\n##|\n\*\*|\Z)',
                content,
                re.DOTALL | re.IGNORECASE,
            )
            if match:
                para = match.group(1).strip()
                # Take first paragraph (up to double newline or single line)
                para = para.split('\n\n')[0].strip()
                para = re.sub(r'\s+', ' ', para)
                if para:
                    description = para
                    break

        # First block of body text if no Purpose/Domain (e.g. single blockquote/paragraph at top)
        if not description and content.strip():
            lines = content.strip().split('\n')
            first_block = []
            for line in lines:
                if line.strip().startswith('#'):
                    break
                if line.strip():
                    first_block.append(line.strip())
            if first_block:
                description = ' '.join(first_block)[:500]

        # Keywords: **Keywords:** or ## Keywords section, comma-separated
        kw_match = re.search(r'\*\*Keywords:\*\*\s*(.+?)(?=\n##|\n\*\*|\Z)', content, re.DOTALL | re.IGNORECASE)
        if not kw_match:
            kw_match = re.search(r'##\s*Keywords\s*\n+(.+?)(?=\n##|\Z)', content, re.DOTALL | re.IGNORECASE)
        if kw_match:
            raw = kw_match.group(1).strip().replace('\n', ' ')
            keywords = [w.strip().lower() for w in re.split(r'[,;]', raw) if w.strip()]
            keywords = list(dict.fromkeys(keywords))[:20]

        return description, keywords
    except Exception as e:
        print(f"Error reading {schema_md}: {e}")
        return None, []


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
        
        # Extract object name from title (supports Table, View, and Function formats)
        name_match = re.search(r'##?\s+(?:\*\*)?(?:Table|View|Function):?(?:\*\*)?\s+(?:`)?\.?\[(\w+)\]\.\[([^\]]+)\]', content)
        if name_match:
            schema_from_title = name_match.group(1)
            object_name = name_match.group(2)
        else:
            schema_from_title = schema_name
            object_name = file_path.stem.split('.')[-1] if '.' in file_path.stem else file_path.stem
        
        # Extract description (the part after the title heading)
        desc_match = re.search(r'##?\s+\*\*(?:Table|View|Function):\*\*\s+`\[[^\]]+\]\.\[[^\]]+\]`\s*\n(?:.*\n)*?>\s+([^\n]+)', content)
        description = desc_match.group(1).strip() if desc_match else ''
        
        # Blockquote fallback for description
        if not description:
            bq_match = re.search(r'^>\s+(.+)$', content, re.MULTILINE)
            description = bq_match.group(1).strip() if bq_match else ''
        
        # Extract usage_example for Function objects
        usage_example = None
        if object_type == 'Function':
            usage_match = re.search(
                r'###\s+\*\*Usage:\*\*\s*\n```sql\n(.+?)\n```',
                content, re.DOTALL
            )
            if usage_match:
                usage_example = usage_match.group(1).strip()
        
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
        
        result = {
            'schema_name': schema_name,
            'object_type': object_type,
            'object_name': object_name,
            'description': description,
            'keywords': keywords,
            'file_name': file_path.name
        }
        if usage_example:
            result['usage_example'] = usage_example
        return result
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None


def generate_object_index(schema_path: Path) -> Dict[str, Any]:
    """Generate .object-index.json for a schema folder"""
    objects = []
    
    # Get all .md files in the schema folder (exclude _schema.md)
    md_files = sorted(f for f in schema_path.glob('*.md') if f.name != '_schema.md')
    
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
        'functions': len([o for o in objects if o['object_type'] == 'Function']),
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

        # Schema-level metadata from _schema.md (purpose/domain and keywords)
        schema_description, schema_keywords = extract_schema_metadata_from_md(schema_folder)

        # Count objects (exclude _schema.md)
        md_files = [f for f in schema_folder.glob('*.md') if f.name != '_schema.md']
        table_count = 0
        view_count = 0
        function_count = 0

        for md_file in md_files:
            metadata = extract_metadata_from_md(md_file)
            if metadata:
                if metadata['object_type'] == 'Table':
                    table_count += 1
                elif metadata['object_type'] == 'View':
                    view_count += 1
                elif metadata['object_type'] == 'Function':
                    function_count += 1

        parts = []
        if table_count: parts.append(f"{table_count} tables")
        if view_count: parts.append(f"{view_count} views")
        if function_count: parts.append(f"{function_count} functions")
        fallback_description = f"Contains {', '.join(parts)}" if parts else "Empty schema"
        schemas.append({
            'schema_name': schema_folder.name,
            'description': schema_description if schema_description else fallback_description,
            'keywords': schema_keywords,
            'object_index_file': f'schemas/{schema_folder.name}/.object-index.json',
            'total_objects': len(md_files),
            'tables': table_count,
            'views': view_count,
            'functions': function_count
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
                    func_count = object_index.get('functions', 0)
                    parts = [f"{object_index['tables']} tables", f"{object_index['views']} views"]
                    if func_count:
                        parts.append(f"{func_count} functions")
                    print(f"    ({', '.join(parts)})")
    
    print(f"\n{'='*60}")
    print("✓ All index files generated successfully!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
