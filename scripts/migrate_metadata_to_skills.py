"""
Migration Script: Move Database Metadata to Skills Files

This script migrates friendly_name, description, and keywords from 
agent_settings.json to _data-source.md in the skills directory.

Usage:
    python scripts/migrate_metadata_to_skills.py
"""

import json
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))


def migrate_metadata():
    """Migrate metadata from agent_settings.json to _data-source.md"""
    
    # Load current agent_settings.json
    config_path = Path("config/agent_settings.json")
    if not config_path.exists():
        print("❌ config/agent_settings.json not found")
        return False
    
    with open(config_path, 'r', encoding='utf-8') as f:
        settings = json.load(f)
    
    # Check if metadata exists in target_db
    target_db = settings.get('target_db', {})
    friendly_name = target_db.get('friendly_name')
    description = target_db.get('description')
    keywords = target_db.get('keywords', [])
    
    if not friendly_name:
        print("⚠️  No friendly_name found in agent_settings.json - metadata may already be migrated")
        return True
    
    print(f"Found metadata in agent_settings.json:")
    print(f"  - Friendly Name: {friendly_name}")
    print(f"  - Description: {description}")
    print(f"  - Keywords: {', '.join(keywords)}")
    
    # Find or create _data-source.md file
    skills_path = Path("skills/data-sources")
    data_source_files = list(skills_path.rglob("_data-source.md"))
    
    if not data_source_files:
        print("\n❌ No _data-source.md file found in skills/data-sources/")
        print("Please create a data source directory first")
        return False
    
    # Use the first _data-source.md found
    data_source_file = data_source_files[0]
    print(f"\nUpdating: {data_source_file}")
    
    # Read current content
    with open(data_source_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse existing metadata
    import re
    
    # Check if metadata already exists
    if '**Friendly Name:**' in content:
        print("⚠️  Metadata already exists in _data-source.md - skipping update")
        return True
    
    # Find the title line
    title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if not title_match:
        print("❌ Could not find title in _data-source.md")
        return False
    
    # Build new metadata section
    type_match = re.search(r'\*\*Type:\*\*\s*(.+)', content)
    server_match = re.search(r'\*\*Server:\*\*\s*(.+)', content)
    database_match = re.search(r'\*\*Database:\*\*\s*(.+)', content)
    
    # Extract existing metadata
    type_line = type_match.group(0) if type_match else "**Type:** SQL Server"
    server_line = server_match.group(0) if server_match else "**Server:** localhost"
    database_line = database_match.group(0) if database_match else "**Database:** database"
    
    # Build new metadata block
    metadata_block = f"""# {friendly_name}

{type_line}  
{server_line}
{database_line}

**Friendly Name:** {friendly_name}  
**Keywords:** {', '.join(keywords)}

## Description

{description}"""
    
    # Replace the section before ## Description
    desc_section_start = content.find('## Description')
    if desc_section_start > 0:
        # Keep everything after ## Description
        after_desc = content[desc_section_start:]
        desc_match = re.search(r'## Description\s*\n(.*?)(?=\n##|\Z)', after_desc, re.DOTALL)
        if desc_match:
            # Remove old description and replace with new one
            after_desc = re.sub(r'## Description\s*\n.*?(?=\n##|\Z)', '', after_desc, flags=re.DOTALL)
        new_content = metadata_block + "\n" + after_desc
    else:
        # No description section, just add it
        new_content = metadata_block + "\n"
    
    # Write updated content
    with open(data_source_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ Updated {data_source_file}")
    
    # Remove metadata from agent_settings.json
    print("\nRemoving metadata from agent_settings.json...")
    
    # Remove the fields
    if 'friendly_name' in target_db:
        del target_db['friendly_name']
    if 'description' in target_db:
        del target_db['description']
    if 'keywords' in target_db:
        del target_db['keywords']
    
    # Write back to file
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)
    
    print(f"✅ Removed metadata from {config_path}")
    print("\n✅ Migration complete!")
    print("\nNext steps:")
    print("1. Review the updated _data-source.md file")
    print("2. Restart the application to use the new configuration")
    
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("  Database Metadata Migration to Skills")
    print("=" * 60)
    print()
    
    success = migrate_metadata()
    
    if not success:
        print("\n❌ Migration failed")
        sys.exit(1)
    else:
        print("\n✅ Migration successful")
        sys.exit(0)
