"""
Cleanup Script: Remove Unused Sections from Existing Markdown Files

This script removes unused sections from existing markdown files in the skills directory:
- For table schema files: removes Era, Record Count, Update Frequency, and empty sections
- For data group files: removes Status field and empty sections

Usage:
    python scripts/cleanup_markdown_files.py [--dry-run] [--path skills/data-sources]
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def clean_table_schema_file(file_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Clean a table schema markdown file by removing unused sections.
    
    Removes:
    - **Era:** Unknown
    - **Record Count:** Unknown
    - **Update Frequency:** Unknown
    - ## Columns (empty section after Description)
    - ## Common Queries section
    - ## Related Tables section
    - ## Data Quality Notes section
    
    Keeps:
    - # Table: [schema].[table]
    - **Data Source:** 
    - **Schema:**
    - **Type:**
    - ## Description (and all content within)
    
    Returns:
        Tuple of (changed, message)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # Remove Era, Record Count, Update Frequency lines
        content = re.sub(r'\*\*Era:\*\*[^\n]*\n', '', content)
        content = re.sub(r'\*\*Record Count:\*\*[^\n]*\n', '', content)
        content = re.sub(r'\*\*Update Frequency:\*\*[^\n]*\n', '', content)
        
        # Remove empty ## Columns section (appears after Description section)
        # Pattern: ## Columns followed by optional whitespace and then either another ## or end of file
        content = re.sub(r'\n## Columns\s*\n(?=\n##|\Z)', '', content)
        
        # Remove ## Common Queries section and its content
        content = re.sub(r'\n## Common Queries\s*\n+\(Requires manual documentation\)\s*\n', '', content)
        
        # Remove ## Related Tables section and its content
        content = re.sub(r'\n## Related Tables\s*\n+\(Requires manual documentation\)\s*\n', '', content)
        
        # Remove ## Data Quality Notes section and its content
        content = re.sub(r'\n## Data Quality Notes\s*\n+\(Requires manual documentation\)\s*\n', '', content)
        
        # Clean up multiple consecutive newlines (more than 2)
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Ensure file ends with single newline
        content = content.rstrip() + '\n'
        
        if content != original_content:
            if not dry_run:
                file_path.write_text(content, encoding='utf-8')
            return True, "Cleaned"
        else:
            return False, "No changes needed"
            
    except Exception as e:
        return False, f"Error: {e}"


def clean_data_group_file(file_path: Path, dry_run: bool = False) -> Tuple[bool, str]:
    """
    Clean a data group markdown file by removing unused sections.
    
    Removes:
    - **Status:** Active
    - **WARNING** Manual Enhancement Needed block
    - ## Common Use Cases section
    - ## Related Data Groups section
    
    Keeps:
    - # Data Group Name
    - **Data Source:**
    - **Category:**
    - **Keywords:**
    - ## Description (and all content)
    - ## Data Objects (and all content)
    
    Returns:
        Tuple of (changed, message)
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # Remove Status line
        content = re.sub(r'\*\*Status:\*\*[^\n]*\n', '', content)
        
        # Remove WARNING block (multi-line)
        warning_pattern = r'\n\*\*WARNING\*\* Manual Enhancement Needed:\s*\n(?:- [^\n]+\n)+'
        content = re.sub(warning_pattern, '\n', content)
        
        # Remove ## Common Use Cases section
        content = re.sub(r'\n## Common Use Cases\s*\n+\(Requires manual documentation\)\s*\n', '', content)
        
        # Remove ## Related Data Groups section
        content = re.sub(r'\n## Related Data Groups\s*\n+\(Requires manual documentation\)\s*\n', '', content)
        
        # Clean up multiple consecutive newlines (more than 2)
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Ensure file ends with single newline
        content = content.rstrip() + '\n'
        
        if content != original_content:
            if not dry_run:
                file_path.write_text(content, encoding='utf-8')
            return True, "Cleaned"
        else:
            return False, "No changes needed"
            
    except Exception as e:
        return False, f"Error: {e}"


def cleanup_markdown_files(base_path: str, dry_run: bool = False):
    """
    Main cleanup function
    
    Args:
        base_path: Base path to skills/data-sources directory
        dry_run: If True, only print what would be done without modifying files
    """
    print("=" * 70)
    print("Markdown Files Cleanup Script")
    print("=" * 70)
    
    base_dir = Path(base_path)
    
    if not base_dir.exists():
        print(f"\n[ERROR] Path does not exist: {base_dir.absolute()}")
        return
    
    if dry_run:
        print("\n[DRY RUN] MODE - No files will be modified\n")
    else:
        print(f"\n[OUTPUT] Processing files in: {base_dir.absolute()}\n")
    
    # Find all markdown files
    table_schema_files = list(base_dir.glob("*/schemas/**/*.md"))
    data_group_files = list(base_dir.glob("*/data-groups/_*-group.md"))
    
    print(f"[INFO] Found {len(table_schema_files)} table schema files")
    print(f"[INFO] Found {len(data_group_files)} data group files")
    print()
    
    # Process table schema files
    print("-" * 70)
    print("Processing Table Schema Files")
    print("-" * 70)
    
    table_changed = 0
    table_unchanged = 0
    table_errors = 0
    
    for file_path in sorted(table_schema_files):
        changed, message = clean_table_schema_file(file_path, dry_run)
        
        if changed:
            table_changed += 1
            status = "[CLEANED]" if not dry_run else "[WOULD CLEAN]"
            print(f"{status} {file_path.relative_to(base_dir)}")
        elif "Error" in message:
            table_errors += 1
            print(f"[ERROR] {file_path.relative_to(base_dir)}: {message}")
        else:
            table_unchanged += 1
            # Don't print unchanged files to reduce noise
    
    print(f"\nTable Schema Files: {table_changed} cleaned, {table_unchanged} unchanged, {table_errors} errors")
    
    # Process data group files
    print("\n" + "-" * 70)
    print("Processing Data Group Files")
    print("-" * 70)
    
    group_changed = 0
    group_unchanged = 0
    group_errors = 0
    
    for file_path in sorted(data_group_files):
        changed, message = clean_data_group_file(file_path, dry_run)
        
        if changed:
            group_changed += 1
            status = "[CLEANED]" if not dry_run else "[WOULD CLEAN]"
            print(f"{status} {file_path.relative_to(base_dir)}")
        elif "Error" in message:
            group_errors += 1
            print(f"[ERROR] {file_path.relative_to(base_dir)}: {message}")
        else:
            group_unchanged += 1
            # Don't print unchanged files to reduce noise
    
    print(f"\nData Group Files: {group_changed} cleaned, {group_unchanged} unchanged, {group_errors} errors")
    
    # Summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Total files processed: {len(table_schema_files) + len(data_group_files)}")
    print(f"Total files cleaned: {table_changed + group_changed}")
    print(f"Total files unchanged: {table_unchanged + group_unchanged}")
    print(f"Total errors: {table_errors + group_errors}")
    
    if dry_run:
        print("\n[INFO] Run without --dry-run to actually modify files")
    else:
        print("\n[SUCCESS] Cleanup complete!")


def main():
    parser = argparse.ArgumentParser(description='Cleanup unused sections from markdown files')
    parser.add_argument('--path', default='skills/data-sources',
                       help='Path to skills/data-sources directory (default: skills/data-sources)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Print what would be done without modifying files')
    
    args = parser.parse_args()
    
    cleanup_markdown_files(args.path, args.dry_run)


if __name__ == '__main__':
    main()
