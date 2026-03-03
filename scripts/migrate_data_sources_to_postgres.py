"""
Migration script to import existing data sources into PostgreSQL registry.

This script:
1. Loads all data sources from skills/data-sources/
2. Extracts their source_id, name, type, and connection info
3. Inserts them into the data_source_registry table
4. Preserves original creation timestamps from file metadata

Run once during initial deployment.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import logging
import re

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.user_database import get_user_db_session, Base, engine
from app.services.data_source_registry_service import DataSourceRegistryService, compute_data_source_identity_hash
from app.services.skills_service import SkillsService
from app.models.user_models import DataSourceRegistry

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def migration_needed() -> bool:
    """
    Check if migration is needed (registry table is empty).
    
    Returns:
        True if migration should run, False otherwise
    """
    try:
        with get_user_db_session() as db_session:
            count = db_session.query(DataSourceRegistry).count()
            return count == 0
    except Exception as e:
        logger.error(f"Error checking migration status: {e}")
        return False


def run_migration():
    """
    Migrate all existing data sources to PostgreSQL registry.
    
    This function:
    - Loads all data sources from filesystem
    - Extracts metadata from _data-source.md files
    - Computes identity hashes
    - Inserts into data_source_registry table
    """
    logger.info("Starting data source migration to PostgreSQL...")
    
    # Ensure table exists
    Base.metadata.create_all(bind=engine)
    
    # Load data sources from filesystem
    try:
        skills_service = SkillsService()
        data_sources = skills_service.load_data_sources_index()
        
        if not data_sources:
            logger.info("No data sources found to migrate")
            return
        
        logger.info(f"Found {len(data_sources)} data sources to migrate")
        
        migrated_count = 0
        skipped_count = 0
        
        with get_user_db_session() as db_session:
            for ds in data_sources:
                try:
                    # Check if already exists
                    existing = db_session.query(DataSourceRegistry).filter(
                        DataSourceRegistry.source_id == ds.source_id
                    ).first()
                    
                    if existing:
                        logger.info(f"Skipping '{ds.name}' - already in registry")
                        skipped_count += 1
                        continue
                    
                    # Extract connection info from data source
                    connection_info = {}
                    if ds.connection_info:
                        connection_info = ds.connection_info
                    
                    # Compute identity hash
                    identity_hash = compute_data_source_identity_hash(
                        ds.name,
                        ds.type,
                        connection_info if connection_info else None
                    )
                    
                    # Get file creation time if available
                    created_at = datetime.utcnow()
                    if ds.file_path and os.path.exists(ds.file_path):
                        file_stat = os.stat(ds.file_path)
                        created_at = datetime.fromtimestamp(file_stat.st_ctime)
                    
                    # Create registry entry
                    entry = DataSourceRegistry(
                        source_id=ds.source_id,
                        name=ds.name,
                        type=ds.type,
                        identity_hash=identity_hash,
                        connection_info=connection_info if connection_info else None,
                        file_path=ds.file_path,
                        created_at=created_at,
                        last_seen_at=datetime.utcnow(),
                        deleted_at=None  # All migrated sources are active
                    )
                    
                    db_session.add(entry)
                    migrated_count += 1
                    logger.info(f"Migrated '{ds.name}' (ID: {ds.source_id})")
                    
                except Exception as e:
                    logger.error(f"Error migrating data source '{ds.name}': {e}")
                    continue
            
            # Commit all changes
            db_session.commit()
            logger.info(f"Migration complete: {migrated_count} migrated, {skipped_count} skipped")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    """Run migration when script is executed directly"""
    if migration_needed():
        run_migration()
        print("\n✅ Migration completed successfully")
    else:
        print("\n⏭️  Migration not needed - registry already contains data")
