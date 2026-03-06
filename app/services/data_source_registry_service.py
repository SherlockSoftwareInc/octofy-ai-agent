"""
Data Source Registry Service - Manages persistent data source ID tracking

This service ensures data source IDs remain stable across delete/recreate cycles
by storing them in PostgreSQL. Uses connection details as a natural key for
identity matching.
"""

import hashlib
import os
import uuid
from datetime import datetime
from typing import Dict, Optional, List, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.user_models import DataSourceRegistry
import logging

logger = logging.getLogger(__name__)


def compute_data_source_identity_hash(name: str, ds_type: str, connection_info: Optional[Dict[str, Any]]) -> str:
    """
    Compute stable identity hash based on data source type and connection details.
    
    This hash is used as the natural key to determine if a data source with the
    same connection has been created before.
    
    Args:
        name: Data source name
        ds_type: Data source type ("SQL Server", "Excel", etc.)
        connection_info: Connection metadata (server, database, file_path, etc.)
        
    Returns:
        SHA256 hash string (64 characters)
    """
    connection_info = connection_info or {}
    
    if ds_type == "SQL Server":
        # Use server + database as natural key (case-insensitive)
        server = connection_info.get("server", "").lower().strip()
        database = connection_info.get("database", "").lower().strip()
        
        if not server or not database:
            # Fallback to name-based key if connection info incomplete
            key = f"sql:{name.lower()}"
        else:
            key = f"sql:{server}:{database}"
            
    elif ds_type == "Excel":
        # Use file path or file hash as natural key
        file_path = connection_info.get("file_path", "").strip()
        
        if file_path and os.path.exists(file_path):
            # Compute MD5 of file content for content-based identity
            try:
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()
                key = f"excel:{file_hash}"
            except Exception as e:
                logger.warning(f"Could not read Excel file {file_path}: {e}")
                key = f"excel:{file_path.lower()}"
        else:
            # Fallback to file path or name
            key = f"excel:{file_path.lower() if file_path else name.lower()}"
            
    else:
        # Fallback: use type + name combination
        key = f"{ds_type.lower()}:{name.lower()}"
    
    # Return SHA256 hash of the key
    return hashlib.sha256(key.encode('utf-8')).hexdigest()


class DataSourceRegistryService:
    """Service for managing data source ID persistence in PostgreSQL"""
    
    def __init__(self, db_session: Session):
        """
        Initialize the registry service.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
    
    def get_or_create_source_id(
        self,
        name: str,
        ds_type: str,
        connection_info: Optional[Dict[str, Any]],
        file_path: Optional[str] = None
    ) -> str:
        """
        Get existing source_id or create new one based on identity hash.
        
        If a data source with the same connection details existed before (even if deleted),
        its UUID is reused. Otherwise, generates a new UUID v4.
        
        Args:
            name: Data source name
            ds_type: Data source type
            connection_info: Connection metadata
            file_path: Filesystem path to _data-source.md
            
        Returns:
            source_id (UUID string) - either existing or newly generated
        """
        identity_hash = compute_data_source_identity_hash(name, ds_type, connection_info)
        
        # Check if this data source identity exists
        existing = self.db.query(DataSourceRegistry).filter(
            DataSourceRegistry.identity_hash == identity_hash
        ).first()
        
        if existing:
            # Reuse existing ID
            logger.info(
                f"Reusing existing source_id '{existing.source_id}' for '{name}' "
                f"(previously created at {existing.created_at})"
            )
            
            # Update metadata for "resurrection"
            existing.name = name  # Update name in case it changed
            existing.deleted_at = None  # Mark as active again
            existing.last_seen_at = datetime.utcnow()
            existing.file_path = file_path
            existing.connection_info = connection_info
            self.db.commit()
            
            return existing.source_id
        else:
            # Create new entry with fresh UUID
            new_source_id = str(uuid.uuid4())
            
            logger.info(f"Creating new source_id '{new_source_id}' for '{name}'")
            
            new_entry = DataSourceRegistry(
                source_id=new_source_id,
                name=name,
                type=ds_type,
                identity_hash=identity_hash,
                connection_info=connection_info,
                file_path=file_path,
                created_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow()
            )
            
            self.db.add(new_entry)
            self.db.commit()
            
            return new_source_id
    
    def mark_deleted(self, source_id: str) -> bool:
        """
        Mark a data source as deleted (soft delete).
        
        Args:
            source_id: UUID of the data source
            
        Returns:
            True if found and marked, False if not found
        """
        entry = self.db.query(DataSourceRegistry).filter(
            DataSourceRegistry.source_id == source_id
        ).first()
        
        if entry:
            entry.deleted_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Marked data source '{entry.name}' (ID: {source_id}) as deleted")
            return True
        else:
            logger.warning(f"Could not find source_id '{source_id}' to mark as deleted")
            return False
    
    def update_last_seen(self, source_id: str):
        """
        Update last_seen_at timestamp (for tracking usage).
        
        Args:
            source_id: UUID of the data source
        """
        entry = self.db.query(DataSourceRegistry).filter(
            DataSourceRegistry.source_id == source_id
        ).first()
        
        if entry:
            entry.last_seen_at = datetime.utcnow()
            self.db.commit()
    
    def find_by_source_id(self, source_id: str) -> Optional[DataSourceRegistry]:
        """
        Find registry entry by source_id.
        
        Args:
            source_id: UUID to look up
            
        Returns:
            DataSourceRegistry entry or None
        """
        return self.db.query(DataSourceRegistry).filter(
            DataSourceRegistry.source_id == source_id
        ).first()
    
    def find_active_by_name(self, name: str) -> Optional[DataSourceRegistry]:
        """
        Find active (non-deleted) data source by name.
        
        Args:
            name: Data source name (case-insensitive)
            
        Returns:
            DataSourceRegistry entry or None
        """
        return self.db.query(DataSourceRegistry).filter(
            and_(
                DataSourceRegistry.name.ilike(name),
                DataSourceRegistry.deleted_at.is_(None)
            )
        ).first()
    
    def find_by_connection_info(
        self,
        server: Optional[str] = None,
        database: Optional[str] = None,
        file_path: Optional[str] = None
    ) -> Optional[DataSourceRegistry]:
        """
        Find data source by connection details.
        
        Supports two lookup patterns:
        - SQL Server: server + database (case-insensitive)
        - Excel/File: file_path (case-sensitive)
        
        Args:
            server: Server name (SQL Server)
            database: Database name (SQL Server)
            file_path: File path (Excel/file-based sources)
            
        Returns:
            DataSourceRegistry entry or None if not found
        """
        from sqlalchemy import func
        
        # SQL Server lookup
        if server and database:
            logger.info(f"Looking up SQL Server data source: {server}\\{database}")
            
            entry = self.db.query(DataSourceRegistry).filter(
                and_(
                    func.lower(DataSourceRegistry.connection_info['server'].astext) == server.lower(),
                    func.lower(DataSourceRegistry.connection_info['database'].astext) == database.lower(),
                    DataSourceRegistry.deleted_at.is_(None)
                )
            ).first()
            
            if entry:
                logger.info(f"Found data source '{entry.name}' (ID: {entry.source_id})")
            else:
                logger.warning(f"No active data source found for {server}\\{database}")
            
            return entry
        
        # Excel/File lookup
        if file_path:
            logger.info(f"Looking up file-based data source: {file_path}")
            
            entry = self.db.query(DataSourceRegistry).filter(
                and_(
                    DataSourceRegistry.connection_info['file_path'].astext == file_path,
                    DataSourceRegistry.deleted_at.is_(None)
                )
            ).first()
            
            if entry:
                logger.info(f"Found data source '{entry.name}' (ID: {entry.source_id})")
            else:
                logger.warning(f"No active data source found for file: {file_path}")
            
            return entry
        
        logger.warning("No valid lookup parameters provided")
        return None
    
    def resolve_source_id(self, source_id: str) -> Optional[str]:
        """
        Resolve source_id, attempting to find active replacement if deleted.
        
        This is used when executing old SQL from conversations where the
        original data source was deleted and recreated.
        
        Args:
            source_id: UUID from old conversation
            
        Returns:
            Active source_id (may be same or new) or None if cannot resolve
        """
        entry = self.find_by_source_id(source_id)
        
        if entry:
            if entry.deleted_at is None:
                # Still active
                return source_id
            else:
                # Deleted - try to find active replacement with same identity
                replacement = self.db.query(DataSourceRegistry).filter(
                    and_(
                        DataSourceRegistry.identity_hash == entry.identity_hash,
                        DataSourceRegistry.deleted_at.is_(None)
                    )
                ).first()
                
                if replacement:
                    logger.info(
                        f"Resolved deleted source '{entry.name}' (ID: {source_id}) "
                        f"to active source (ID: {replacement.source_id})"
                    )
                    return replacement.source_id
                else:
                    logger.warning(
                        f"Data source '{entry.name}' (ID: {source_id}) was deleted "
                        f"and has not been recreated"
                    )
                    return None
        else:
            logger.warning(f"Unknown source_id '{source_id}' not found in registry")
            return None
    
    def list_all(self, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """
        List all data sources in the registry.
        
        Args:
            include_deleted: Whether to include soft-deleted sources
            
        Returns:
            List of dictionaries with registry info
        """
        query = self.db.query(DataSourceRegistry)
        
        if not include_deleted:
            query = query.filter(DataSourceRegistry.deleted_at.is_(None))
        
        entries = query.order_by(DataSourceRegistry.created_at.desc()).all()
        
        return [
            {
                "source_id": e.source_id,
                "name": e.name,
                "type": e.type,
                "identity_hash": e.identity_hash,
                "connection_info": e.connection_info,
                "file_path": e.file_path,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "deleted_at": e.deleted_at.isoformat() if e.deleted_at else None,
                "last_seen_at": e.last_seen_at.isoformat() if e.last_seen_at else None,
                "status": "deleted" if e.deleted_at else "active"
            }
            for e in entries
        ]
