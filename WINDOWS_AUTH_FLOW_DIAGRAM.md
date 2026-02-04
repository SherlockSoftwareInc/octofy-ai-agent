# Windows Authentication Flow - Visual Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                     USER REQUESTS PYTHON CODE                        │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  API Endpoint: POST /api/v1/execute-python                          │
│  File: app/api/endpoints/generation.py                              │
│                                                                      │
│  1. Load settings.target_db.python_connection_string_encrypted      │
│  2. Decrypt connection string                                       │
│  3. Inject into exec_context['DB_CONNECTION_STRING']                │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Decrypted Connection String (SQLAlchemy URL Format):               │
│                                                                      │
│  Driver={ODBC Driver 17 for SQL Server};                            │
│  Server=localhost;                                                  │
│  Database=northwind;                                                │
│  Encrypt=yes;                                                       │
│  TrustServerCertificate=yes;                                        │
│  Trusted_Connection=yes  ← WINDOWS AUTHENTICATION                   │
│                                                                      │
│  ✅ NO UID (username)                                               │
│  ✅ NO PWD (password)                                               │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Execution Service: execute_python_code()                           │
│  File: app/services/execution_service.py                            │
│                                                                      │
│  • Receives DB_CONNECTION_STRING in context parameter               │
│  • Logs masked version for security                                 │
│  • Injects into execution scope for user code                       │
│  • Executes user's Python code with proper globals/locals           │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  User's Python Code Executes:                                       │
│                                                                      │
│  import sqlalchemy                                                  │
│  import pandas as pd                                                │
│                                                                      │
│  # DB_CONNECTION_STRING is available in scope                       │
│  engine = sqlalchemy.create_engine(DB_CONNECTION_STRING)            │
│                                                                      │
│  # Query executes using Windows Authentication                      │
│  df = pd.read_sql_query("SELECT * FROM Orders", engine)             │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SQL Server Connection                                              │
│                                                                      │
│  • Authentication: Windows (Kerberos/NTLM)                          │
│  • User: SSI01\sherl (current Windows user)                         │
│  • No password transmission                                         │
│  • Integrated Windows security policies                             │
│  • Audit trail in Windows Event Log                                 │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SQL Server: Northwind Database                                     │
│                                                                      │
│  ✅ Query executed successfully                                     │
│  ✅ Results returned to Python code                                 │
│  ✅ DataFrame created and returned to user                          │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Security Features

### 🔒 Configuration Level
- **Auth Type**: Set to `"windows"` in `config/agent_settings.json`
- **No Credentials**: Username field is `null`
- **Encrypted Storage**: Connection strings stored with AES encryption

### 🔒 Code Injection Level
- **Pre-Decrypted**: Connection string decrypted before code execution
- **Context Isolation**: Only injected into specific execution context
- **No String Manipulation**: Direct variable injection (no string concatenation)

### 🔒 Logging Level
- **Masked Output**: Connection strings masked in all log files
- **Security Truncation**: Only first 20 characters shown for debugging
- **No Credential Exposure**: Windows auth has no credentials to expose

### 🔒 Execution Level
- **Sandboxed Scope**: Code executes in controlled global/local scope
- **Limited Variables**: Only necessary variables injected
- **No Persistence**: Connection string exists only during execution

---

## Configuration Sources

### Primary Source
**File**: `config/agent_settings.json`
```json
{
  "target_db": {
    "auth_type": "windows",
    "username": null,
    "connection_string_encrypted": "gAAAAAB...",
    "python_connection_string_encrypted": "gAAAAAB..."
  }
}
```

### Encryption Key
**Location**: Derived from application secret
**Algorithm**: Fernet (symmetric encryption)
**Key Derivation**: PBKDF2 with salt

---

## Authentication Methods Comparison

| Feature | SQL Authentication | Windows Authentication (Current) |
|---------|-------------------|----------------------------------|
| Credentials in Config | ✅ YES (Username/Password) | ❌ NO |
| Password Storage | 🔴 Required (encrypted) | ✅ Not needed |
| Password Rotation | 🔴 Manual process | ✅ Windows policy |
| Audit Trail | 🟡 SQL Server logs only | ✅ Windows + SQL Server |
| Multi-Factor Auth | ❌ Not supported | ✅ Via Windows |
| Centralized Management | ❌ Per-application | ✅ Active Directory |
| Security Risk | 🔴 Higher (credential theft) | ✅ Lower (no credentials) |

---

## Verification Commands

```powershell
# Check authentication type
python -c "from app.services.settings_service import load_settings; s=load_settings(); print(f'Auth: {s.target_db.auth_type}')"

# Verify connection string contents
python scripts\verify_python_execution_auth.py

# Test actual database connection
python scripts\verify_windows_auth.py

# Check current Windows user
python -c "from app.core.database import get_db_engine; from sqlalchemy import text; e=get_db_engine(); c=e.connect(); r=c.execute(text('SELECT SYSTEM_USER')); print(f'Connected as: {r.fetchone()[0]}')"
```

Expected outputs:
```
Auth: windows
✅ VERIFIED: Python code execution uses Windows Authentication
✅ All checks passed! Windows authentication is properly configured.
Connected as: SSI01\sherl
```

---

## Troubleshooting

### Issue: Code execution fails with "Login failed"
**Solution**: Ensure the Windows account running the application has SQL Server permissions

### Issue: "Cannot open database"
**Solution**: Grant the Windows user access to the database:
```sql
CREATE USER [DOMAIN\Username] FOR LOGIN [DOMAIN\Username];
GRANT SELECT ON SCHEMA::dbo TO [DOMAIN\Username];
```

### Issue: Connection works in terminal but not in app
**Solution**: Check that the application service is running under the correct Windows account

---

## Related Files

- `app/api/endpoints/generation.py` - Connection string injection
- `app/services/execution_service.py` - Python code execution
- `app/services/settings_service.py` - Configuration management
- `config/agent_settings.json` - Runtime configuration
- `scripts/verify_python_execution_auth.py` - Verification script
