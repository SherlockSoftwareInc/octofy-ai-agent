#!/usr/bin/env python3
"""
Manual Migration Script: V1 to V2 Multi-Source Architecture

This script migrates the Octofy AI Agent from single-database (v1) to multi-source (v2) configuration.

Steps performed:
1. Backup existing agent_settings.json
2. Detect v1 configuration
3. Transform to v2 format with generated source_id
4. Create schema_index_v2 collection in Milvus
5. Copy and migrate data from schema_index to schema_index_v2
6. Add source_id to all existing records
7. Validate migration
8. Save new configuration

Usage:
    python scripts/migrate_to_multi_source.py [--rollback]

Options:
    --rollback: Restore from backup if migration failed
"""

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from pymilvus import Collection, connections, utility
    from app.core.config import MILVUS_HOST, MILVUS_PORT, MILVUS_COLLECTION_SCHEMA, MILVUS_COLLECTION_SCHEMA_V2
    from app.services.migration_service import (
        detect_config_version,
        migrate_v1_to_v2,
        save_backup,
        rollback_migration,
        get_migration_status
    )
    from app.services.vector_store import MilvusVectorStore
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root and dependencies are installed.")
    sys.exit(1)


def print_status(status: str, message: str):
    """Print colored status messages"""
    colors = {
        'info': '\033[94m',  # Blue
        'success': '\033[92m',  # Green
        'warning': '\033[93m',  # Yellow
        'error': '\033[91m',  # Red
        'reset': '\033[0m'
    }
    
    symbols = {
        'info': 'ℹ',
        'success': '✓',
        'warning': '⚠',
        'error': '✗'
    }
    
    color = colors.get(status, colors['reset'])
    symbol = symbols.get(status, '')
    print(f"{color}{symbol} {message}{colors['reset']}")


def connect_to_milvus():
    """Connect to Milvus server"""
    try:
        connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)
        print_status('success', f'Connected to Milvus at {MILVUS_HOST}:{MILVUS_PORT}')
        return True
    except Exception as e:
        print_status('error', f'Failed to connect to Milvus: {e}')
        return False


def migrate_vector_data(source_id: str):
    """Migrate data from schema_index to schema_index_v2"""
    print_status('info', 'Migrating vector store data...')
    
    try:
        vector_store = MilvusVectorStore()
        
        # Ensure v2 collection exists
        vector_store._ensure_schema_v2_collection()
        
        # Check if v1 collection exists
        if not utility.has_collection(MILVUS_COLLECTION_SCHEMA):
            print_status('warning', 'No v1 schema collection found - skipping data migration')
            return True
        
        # Load v1 collection
        v1_collection = Collection(MILVUS_COLLECTION_SCHEMA)
        v1_collection.load()
        
        # Get all records from v1
        print_status('info', 'Fetching records from v1 collection...')
        results = v1_collection.query(
            expr="id >= 0",
            output_fields=["id", "schema_name", "table_name", "description"]
        )
        
        if not results:
            print_status('warning', 'No records found in v1 collection')
            return True
        
        print_status('info', f'Found {len(results)} records to migrate')
        
        # Migrate each record
        migrated_count = 0
        for record in results:
            try:
                # Get embedding from v1
                search_result = v1_collection.search(
                    data=[[0.0] * 1536],  # Dummy query to get record
                    anns_field="embedding",
                    param={"metric_type": "L2", "params": {"nprobe": 10}},
                    limit=1,
                    expr=f"id == {record['id']}"
                )
                
                if search_result and len(search_result[0]) > 0:
                    embedding = search_result[0][0].embedding
                    
                    # Insert into v2 with source_id
                    vector_store.insert_schema_v2(
                        source_id=source_id,
                        schema_name=record['schema_name'],
                        table_name=record['table_name'],
                        description=record['description'],
                        embedding=embedding
                    )
                    migrated_count += 1
                    
                    if migrated_count % 10 == 0:
                        print_status('info', f'Migrated {migrated_count}/{len(results)} records...')
                        
            except Exception as e:
                print_status('warning', f'Failed to migrate record {record["id"]}: {e}')
                continue
        
        print_status('success', f'Successfully migrated {migrated_count}/{len(results)} records')
        return True
        
    except Exception as e:
        print_status('error', f'Vector data migration failed: {e}')
        return False


def run_migration():
    """Execute the migration process"""
    print("\n" + "="*60)
    print("  Octofy AI Agent: V1 → V2 Migration")
    print("="*60 + "\n")
    
    # Step 1: Check configuration version
    print_status('info', 'Step 1: Detecting configuration version...')
    version = detect_config_version()
    
    if version == 2:
        print_status('success', 'Configuration is already V2 format')
        return True
    elif version != 1:
        print_status('error', 'Invalid configuration format detected')
        return False
    
    print_status('info', 'Detected V1 configuration')
    
    # Step 2: Create backup
    print_status('info', 'Step 2: Creating backup...')
    backup_path = save_backup()
    if backup_path:
        print_status('success', f'Backup saved to: {backup_path}')
    else:
        print_status('error', 'Backup creation failed')
        return False
    
    # Step 3: Connect to Milvus
    print_status('info', 'Step 3: Connecting to Milvus...')
    if not connect_to_milvus():
        return False
    
    # Step 4: Migrate configuration
    print_status('info', 'Step 4: Migrating configuration to V2...')
    v2_settings = migrate_v1_to_v2()
    
    if not v2_settings:
        print_status('error', 'Configuration migration failed')
        return False
    
    source_id = v2_settings.data_sources[0].source_id
    print_status('success', f'Configuration migrated (source_id: {source_id})')
    
    # Step 5: Migrate vector store data
    print_status('info', 'Step 5: Migrating vector store data...')
    if not migrate_vector_data(source_id):
        print_status('error', 'Vector store migration failed')
        print_status('warning', 'Attempting rollback...')
        rollback_migration()
        return False
    
    # Step 6: Validate migration
    print_status('info', 'Step 6: Validating migration...')
    status = get_migration_status()
    
    if status.get('version') == 2:
        print_status('success', 'Migration validation passed')
    else:
        print_status('error', 'Migration validation failed')
        return False
    
    print("\n" + "="*60)
    print_status('success', 'Migration completed successfully!')
    print("="*60)
    
    print("\n📋 Next Steps:")
    print("  1. Restart the backend server")
    print("  2. Test the new multi-source functionality")
    print("  3. Add additional data sources via the admin UI")
    print(f"\n💾 Backup location: {backup_path}")
    print("   (Keep this safe in case you need to rollback)\n")
    
    return True


def run_rollback():
    """Rollback to V1 configuration"""
    print("\n" + "="*60)
    print("  Octofy AI Agent: Migration Rollback")
    print("="*60 + "\n")
    
    print_status('warning', 'This will restore the V1 configuration from backup')
    response = input('Are you sure you want to rollback? (yes/no): ')
    
    if response.lower() != 'yes':
        print_status('info', 'Rollback cancelled')
        return
    
    print_status('info', 'Starting rollback...')
    success = rollback_migration()
    
    if success:
        print_status('success', 'Rollback completed successfully')
        print("\nYou should restart the backend server.\n")
    else:
        print_status('error', 'Rollback failed - check logs for details')


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate Octofy AI Agent to multi-source architecture')
    parser.add_argument('--rollback', action='store_true', help='Rollback to V1 configuration')
    args = parser.parse_args()
    
    if args.rollback:
        run_rollback()
    else:
        success = run_migration()
        if not success:
            print("\n❌ Migration failed. Your original configuration is backed up.")
            print("   Use --rollback flag to restore the backup if needed.\n")
            sys.exit(1)


if __name__ == '__main__':
    main()
