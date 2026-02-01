"""
Migration script: Convert Data Groups section from _data-source.md to .data-groups file

This script:
1. Finds all _data-source.md files in skills/data-sources
2. Extracts the "## Data Groups" section
3. Reads each group markdown file to get the actual title
4. Creates a .data-groups file with format: "Title|filename.md"
5. Removes the "## Data Groups" section from _data-source.md
6. Reports all changes

Usage:
    python scripts/migrate_data_groups_to_file.py [--dry-run]
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional


def extract_data_groups_from_markdown(content: str) -> Tuple[List[str], str]:
    """
    Extract data group filenames from ## Data Groups section
    
    Args:
        content: Full markdown content of _data-source.md
        
    Returns:
        Tuple of (list of group filenames, content without data groups section)
    """
    group_filenames = []
    
    # Find all data group links in the format:
    # ### [data-groups/_contacts-group.md](data-groups/_contacts-group.md)
    pattern = r'###\s+\[data-groups/([_\w\-]+\.md)\]\(data-groups/[_\w\-]+\.md\)'
    matches = re.findall(pattern, content)
    group_filenames.extend(matches)
    
    # Remove the entire ## Data Groups section
    # Pattern: from "## Data Groups" to next "##" section or end of file
    cleaned_content = re.sub(
        r'\n## Data Groups\s*\n.*?(?=\n##|\Z)',
        '',
        content,
        flags=re.DOTALL
    )
    
    return group_filenames, cleaned_content


def read_group_title(group_file_path: Path) -> Optional[str]:
    """
    Read the title from a data group markdown file
    
    Args:
        group_file_path: Path to the _*-group.md file
        
    Returns:
        Title string or None if file doesn't exist or can't be parsed
    """
    if not group_file_path.exists():
        return None
    
    try:
        content = group_file_path.read_text(encoding='utf-8')
        # Extract title from first line: # Title
        title_match = re.search(r'^#\s+(.+?)(?:\s+Data Group)?$', content, re.MULTILINE)
        if title_match:
            title = title_match.group(1).strip()
            # Ensure it ends with "Data Group" for consistency
            if not title.endswith('Data Group'):
                title = f"{title} Data Group"
            return title
    except Exception as e:
        print(f"  [WARNING] Error reading {group_file_path}: {e}")
    
    return None


def create_data_groups_file(ds_dir: Path, group_filenames: List[str], dry_run: bool = False) -> int:
    """
    Create .data-groups file with format: "Title|filename.md"
    
    Args:
        ds_dir: Data source directory
        group_filenames: List of group filenames
        dry_run: If True, only print what would be done
        
    Returns:
        Number of groups written
    """
    data_groups_content = []
    groups_dir = ds_dir / "data-groups"
    
    for filename in group_filenames:
        group_file_path = groups_dir / filename
        title = read_group_title(group_file_path)
        
        if title:
            data_groups_content.append(f"{title}|{filename}")
            if dry_run:
                print(f"    - {title}|{filename}")
        else:
            # Fallback: derive title from filename
            fallback_title = filename.replace('_', '').replace('-group.md', '').title() + " Data Group"
            data_groups_content.append(f"{fallback_title}|{filename}")
            if dry_run:
                print(f"    - {fallback_title}|{filename} [FALLBACK]")
    
    if not dry_run:
        data_groups_file = ds_dir / ".data-groups"
        data_groups_file.write_text('\n'.join(data_groups_content) + '\n', encoding='utf-8')
        print(f"  [SUCCESS] Created {data_groups_file} with {len(data_groups_content)} groups")
    
    return len(data_groups_content)


def migrate_data_source(ds_file: Path, dry_run: bool = False) -> bool:
    """
    Migrate a single _data-source.md file
    
    Args:
        ds_file: Path to _data-source.md
        dry_run: If True, only print what would be done
        
    Returns:
        True if migration was performed, False if skipped
    """
    ds_dir = ds_file.parent
    ds_name = ds_dir.name
    
    print(f"\n[PROCESSING] {ds_name}/_data-source.md")
    
    # Read current content
    content = ds_file.read_text(encoding='utf-8')
    
    # Check if ## Data Groups section exists
    if '## Data Groups' not in content:
        print(f"  [SKIP] No '## Data Groups' section found")
        return False
    
    # Check if .data-groups file already exists
    data_groups_file = ds_dir / ".data-groups"
    if data_groups_file.exists() and not dry_run:
        print(f"  [SKIP] .data-groups file already exists")
        return False
    
    # Extract data groups
    group_filenames, cleaned_content = extract_data_groups_from_markdown(content)
    
    if not group_filenames:
        print(f"  [SKIP] No data groups found in section")
        return False
    
    print(f"  Found {len(group_filenames)} data groups")
    
    # Create .data-groups file
    if dry_run:
        print(f"  [DRY-RUN] Would create .data-groups with:")
    
    num_written = create_data_groups_file(ds_dir, group_filenames, dry_run)
    
    # Update _data-source.md (remove ## Data Groups section)
    if not dry_run:
        ds_file.write_text(cleaned_content, encoding='utf-8')
        print(f"  [SUCCESS] Removed '## Data Groups' section from {ds_file.name}")
    else:
        print(f"  [DRY-RUN] Would remove '## Data Groups' section from {ds_file.name}")
    
    return True


def main():
    """Main migration function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate data groups from _data-source.md to .data-groups file')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--path', default='skills/data-sources', help='Path to skills directory')
    
    args = parser.parse_args()
    
    skills_path = Path(args.path)
    
    if not skills_path.exists():
        print(f"[ERROR] Skills path not found: {skills_path}")
        sys.exit(1)
    
    print(f"[START] Migrating data sources in {skills_path}")
    if args.dry_run:
        print("[DRY-RUN MODE] No changes will be made\n")
    
    # Find all _data-source.md files
    ds_files = list(skills_path.rglob("_data-source.md"))
    
    if not ds_files:
        print(f"[WARNING] No _data-source.md files found in {skills_path}")
        sys.exit(0)
    
    print(f"Found {len(ds_files)} data source(s)\n")
    
    migrated_count = 0
    for ds_file in ds_files:
        if migrate_data_source(ds_file, dry_run=args.dry_run):
            migrated_count += 1
    
    print(f"\n[COMPLETE] Migrated {migrated_count} data source(s)")
    
    if args.dry_run:
        print("\nRe-run without --dry-run to apply changes")


if __name__ == '__main__':
    main()
