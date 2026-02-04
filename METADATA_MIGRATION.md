# Database Metadata Migration to Skills

## Overview

Database metadata (friendly name, description, and keywords) has been moved from `agent_settings.json` to the skills-based data source files (`_data-source.md`). This provides better organization and aligns with the skills-based discovery architecture.

## What Changed

### Before (v1)
```json
{
  "target_db": {
    "friendly_name": "Northwind Database",
    "description": "Sales database for imported and exported specialty foods",
    "keywords": ["sales", "customers", "orders", "products", "employees", "shipping"],
    "server": "localhost",
    "database_name": "northwind",
    // ... other connection settings
  }
}
```

### After (v2)
**agent_settings.json** - Connection settings only:
```json
{
  "target_db": {
    "db_type": "mssql",
    "server": "localhost",
    "database_name": "northwind",
    "connection_string_encrypted": "...",
    "driver": "ODBC Driver 17 for SQL Server",
    "auth_type": "windows",
    // ... other connection settings
  }
}
```

**skills/data-sources/Northwind/_data-source.md** - Metadata and documentation:
```markdown
# Northwind Database

**Type:** SQL Server  
**Server:** localhost
**Database:** northwind

**Friendly Name:** Northwind Database  
**Keywords:** sales, customers, orders, products, employees, shipping

## Description

Sales database for imported and exported specialty foods. This database contains comprehensive information about customer orders, product inventory, employee management, and international shipping operations.
```

## Benefits

1. **Better Organization**: Database documentation is now co-located with schema files
2. **Version Control Friendly**: Metadata changes are tracked separately from connection settings
3. **Skills-Based Discovery**: Metadata is now part of the skills framework for enhanced semantic search
4. **Security**: Sensitive connection strings remain encrypted in config, while documentation is in plain text
5. **Easier Editing**: Edit metadata directly in markdown files without touching JSON configuration

## Migration Steps

### Automatic Migration

Run the migration script to automatically move metadata:

```powershell
python scripts/migrate_metadata_to_skills.py
```

This will:
1. Read metadata from `agent_settings.json`
2. Update `_data-source.md` with the metadata
3. Remove metadata fields from `agent_settings.json`
4. Preserve all connection settings

### Manual Migration

If you prefer to migrate manually:

1. **Open your _data-source.md file** (e.g., `skills/data-sources/Northwind/_data-source.md`)

2. **Add metadata section** after the header:
   ```markdown
   # [Your Database Name]
   
   **Type:** SQL Server  
   **Server:** localhost
   **Database:** northwind
   
   **Friendly Name:** [Your Friendly Name]  
   **Keywords:** [keyword1, keyword2, keyword3]
   
   ## Description
   
   [Your database description]
   ```

3. **Open config/agent_settings.json**

4. **Remove these fields** from `target_db`:
   - `friendly_name`
   - `description`
   - `keywords`

5. **Save both files**

## Code Changes

### Backend Changes

1. **app/models/schemas.py**: Removed `friendly_name`, `description`, `keywords` from `TargetDBConfig`
2. **app/services/settings_service.py**: Removed metadata from default settings
3. **app/services/generation_service.py**: Now loads metadata from skills service instead of settings
4. **app/services/skills_service.py**: Added `load_primary_data_source()` and `_parse_data_source_file()` methods

### Frontend Changes

1. **frontend/src/pages/Admin/Settings.tsx**: Removed metadata input fields from Target Database section
2. **frontend/src/api/client.ts**: Updated `TargetDBConfig` interface to remove metadata fields

## API Impact

### No Breaking Changes for:
- Connection testing endpoints
- Database query execution
- Schema synchronization
- All other database operations

### Changed Behavior:
- `GET /api/v1/settings`: No longer returns `friendly_name`, `description`, `keywords` in `target_db`
- SQL generation now reads metadata from skills files automatically
- Settings UI no longer shows metadata input fields (now read-only note)

## Backward Compatibility

The system gracefully handles both old and new formats:

1. **If metadata exists in agent_settings.json**: Will still work (fallback behavior)
2. **If metadata exists in _data-source.md**: Preferred source (takes precedence)
3. **If neither exists**: Uses default fallback values ("Database", "Primary database", [])

## Troubleshooting

### Issue: "Database metadata not loading"

**Check:**
```powershell
python -c "from app.services.skills_service import get_skills_service; ds = get_skills_service().load_primary_data_source(); print(ds)"
```

**Solution:** Ensure `_data-source.md` exists with proper formatting

### Issue: "Keywords not appearing in prompts"

**Check:** Verify keywords are comma-separated in the markdown file:
```markdown
**Keywords:** sales, customers, orders
```

### Issue: "Old metadata still showing"

**Solution:** Remove old fields from `agent_settings.json` and restart the application

## Files Modified

### Backend
- `app/models/schemas.py`
- `app/services/settings_service.py`
- `app/services/generation_service.py`
- `app/services/skills_service.py`
- `config/agent_settings.json`

### Frontend
- `frontend/src/pages/Admin/Settings.tsx`
- `frontend/src/api/client.ts`

### Documentation
- `skills/data-sources/Northwind/_data-source.md`

### Scripts
- `scripts/migrate_metadata_to_skills.py` (new)

## Future Enhancements

1. **UI for Editing _data-source.md**: Add markdown editor in admin panel
2. **Multi-Source Support**: Extend to support multiple data sources with individual metadata
3. **Validation**: Add schema validation for _data-source.md format
4. **Auto-Generation**: Generate initial _data-source.md from database introspection

## Questions?

If you encounter issues:
1. Check `_data-source.md` formatting matches the examples above
2. Verify skills service can load the file (see troubleshooting section)
3. Review console output for parsing errors
4. Check that `agent_settings.json` no longer contains metadata fields
