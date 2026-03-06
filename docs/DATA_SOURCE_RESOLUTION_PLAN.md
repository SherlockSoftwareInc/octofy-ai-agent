# Data Source Resolution Service Implementation Plan

**Status:** In Progress  
**Created:** March 6, 2026  
**Feature:** Add data source name to ID resolution endpoint

---

## Overview

This enhancement adds a new endpoint to resolve data source connection details (server + database for SQL Server, file_path for Excel) to their corresponding source IDs. Users can call this endpoint first, then use the returned source_id with existing discovery and generate-sql services without modification.

## Summary

Create a new `GET /api/v1/data-sources/resolve` endpoint that accepts separate `server` and `database` query parameters (for SQL Server) or `file_path` (for Excel), looks up the source_id from `DataSourceRegistry` with case-insensitive matching, and returns the resolved source_id. Returns 404 if not found, 400 if invalid parameter combination. No changes needed to existing discovery or generate-sql endpoints.

---

## Implementation Steps

### Step 1: Add Resolution Method to DataSourceRegistryService

**File:** `app/services/data_source_registry_service.py`  
**Location:** Add after line 75 (in `DataSourceRegistryService` class)

Add new method `find_by_connection_info()`:

```python
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
    from sqlalchemy import func, and_
    
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
```

---

### Step 2: Create Response Schema

**File:** `app/models/schemas.py`  
**Location:** Add near other data source schemas (around line 630)

Add new response schema:

```python
class ResolveDataSourceResponse(BaseModel):
    """Response schema for data source resolution."""
    source_id: str = Field(..., description="Resolved data source GUID")
    name: str = Field(..., description="Friendly name of the data source")
    type: str = Field(..., description="Data source type: SQL Server, Excel, etc.")
    server: Optional[str] = Field(None, description="Server name (for SQL Server)")
    database: Optional[str] = Field(None, description="Database name (for SQL Server)")
    file_path: Optional[str] = Field(None, description="File path (for Excel)")
    status: str = Field(default="active", description="Data source status")
    object_count: int = Field(default=0, description="Number of indexed objects")
```

---

### Step 3: Create Resolution Endpoint

**File:** `app/api/endpoints/data_sources.py`  
**Location:** Add at the end of the router definitions (before the helper functions section)

Add new endpoint - see plan for full implementation.

---

### Step 4: Update API Documentation

**File:** `docs/BACKEND_API.md`  
**Location:** Add new subsection under "Multi-Source Management"

See full documentation in plan.

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Separate parameters** | Cleaner API design - server/database/file_path as individual query params |
| **Type-aware validation** | Different validation rules for SQL Server vs Excel lookups |
| **GET method** | RESTful design for lookup/query operations |
| **Case-insensitive SQL Server matching** | User-friendly, matches SQL Server conventions |
| **Case-sensitive file path matching** | Respects filesystem conventions |
| **Admin-only** | Requires admin authentication to prevent unauthorized data source enumeration |
| **Active sources only** | Excludes soft-deleted sources to prevent stale references |

---

## Verification Steps

See plan for detailed verification commands.

---

## Future Enhancements

- [ ] Cache resolved source_ids on client side
- [ ] Add metrics/telemetry for resolution success rates
- [ ] Support additional data source types
- [ ] Add batch resolution endpoint
