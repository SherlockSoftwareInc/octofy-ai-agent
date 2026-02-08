# Windows Authentication Migration Summary

## Date: February 3, 2026

## Overview
All SQL Server connections have been changed from SQL authentication to Windows authentication (Trusted_Connection).

## Changes Made

### 1. Schema Models (`app/models/schemas.py`)
- **TargetDBConfig**: Changed default `auth_type` from `"sql"` to `"windows"`
- **ConnectionTestRequest**: Changed default `auth_type` from `"sql"` to `"windows"`
- **AddDataSourceRequest**: Changed default `auth_type` from `"sql"` to `"windows"`

### 2. Settings Service (`app/services/settings_service.py`)
- **get_default_settings()**: Changed default `auth_type` from `"sql"` to `"windows"`

### 3. Configuration Architecture
- Moved database config from `agent_settings.json` to `skills/_data-source.md` files
- Application config now in `.env` file (LLM, embedding, vector settings)
- Connection strings built dynamically from markdown metadata
- Windows authentication enabled by default in `app/core/database.py`

### 4. Environment Template (`.env.example`)
- Updated documentation to show Windows authentication as default
- Added example showing `Trusted_Connection=yes` format
- Kept SQL auth example as alternative

### 5. Connection String Update Script
- Created `scripts/update_to_windows_auth.py` to automate the migration
- Script rebuilds and re-encrypts connection strings with Windows authentication

## Technical Details

### Connection String Format
**Windows Authentication:**
```
Driver={ODBC Driver 17 for SQL Server};
Server=localhost;
Database=northwind;
Encrypt=yes;
TrustServerCertificate=yes;
Trusted_Connection=yes
```

**Previous SQL Authentication:**
```
Driver={ODBC Driver 17 for SQL Server};
Server=localhost;
Database=northwind;
Encrypt=yes;
TrustServerCertificate=yes;
UID=sql_agent;
PWD=<password>
```

## Requirements

### Windows Authentication Prerequisites
1. **Windows OS**: The application must run on Windows or a Windows-compatible environment
2. **Domain/Local Account**: The account running the application must have:
   - Windows login credentials
   - SQL Server login permissions
   - Appropriate database permissions (SELECT, INSERT, UPDATE, etc.)
3. **Network Configuration**: If SQL Server is remote, Kerberos/NTLM authentication must be enabled

### SQL Server Configuration
1. Enable Windows Authentication mode (or Mixed Mode)
2. Create a Windows login for the service account
3. Grant necessary database permissions to the Windows login

Example SQL to grant permissions:
```sql
-- Create login from Windows account
CREATE LOGIN [DOMAIN\Username] FROM WINDOWS;

-- Grant access to database
USE Northwind;
CREATE USER [DOMAIN\Username] FOR LOGIN [DOMAIN\Username];

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::dbo TO [DOMAIN\Username];
```

## Testing

### Verify Connection
1. Run the update script:
   ```powershell
   python scripts\update_to_windows_auth.py
   ```

2. Test connection via API:
   ```bash
   curl -X POST http://localhost:8000/api/v1/settings/test-connection \
     -H "Content-Type: application/json" \
     -d '{
       "driver": "ODBC Driver 17 for SQL Server",
       "server": "localhost",
       "database": "northwind",
       "auth_type": "windows",
       "trust_server_certificate": true
     }'
   ```

3. Verify application startup:
   ```powershell
   uvicorn app.main:app --reload
   ```

4. Test discovery and SQL generation through the web UI

## Rollback Procedure

Windows authentication is now the default. To use SQL authentication for specific data sources:

1. Edit the data source's `_data-source.md` file to add authentication details
2. Update `app/core/database.py` to support multiple auth types per source
3. Store SQL credentials securely in `.env` if needed

**Note**: The old `agent_settings.json` configuration file no longer exists. Configuration is now split between:
- `.env` - Application settings (LLM, embedding, vector)
- `skills/_data-source.md` - Database connection metadata

## Security Considerations

### Advantages of Windows Authentication
- ✅ No passwords stored in configuration files
- ✅ Uses Windows security policies (password expiration, complexity, etc.)
- ✅ Integrated with Active Directory for centralized management
- ✅ Supports Kerberos for secure authentication
- ✅ Audit trail through Windows Event Logs

### Important Notes
- The application must run under a Windows account with database permissions
- For service deployment, use a dedicated service account with minimal required permissions
- Ensure the service account password doesn't expire or has an exemption
- For containerized deployments (Docker), consider using gMSA (Group Managed Service Accounts)

## Files Modified

1. `app/models/schemas.py` - Updated default auth_type in 3 model classes
2. `app/services/settings_service.py` - Removed agent_settings.json, now uses `.env`
3. `app/core/database.py` - Builds connection strings from skills metadata
4. `skills/data-sources/*/data-source.md` - Data source definitions
5. `.env` - Application configuration (LLM, embedding, vector settings)

## Next Steps

1. ✅ Changes applied
2. ⏳ Test database connection
3. ⏳ Restart application services
4. ⏳ Verify end-to-end functionality (discovery, SQL generation, execution)
5. ⏳ Update deployment documentation if using Docker or other container platforms
