# Getting Started with User Management

This guide will help you set up and test the new user management system for Octofy AI Agent.

## Backend Setup (5 minutes)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

**New dependencies added:**
- `psycopg2-binary` - PostgreSQL database adapter
- `python-jose[cryptography]` - JWT token creation/validation
- `passlib[bcrypt]` - Secure password hashing

### Step 2: Start PostgreSQL

**Using Docker (Recommended):**
```bash
# Start PostgreSQL container
docker-compose up -d postgres

# Verify it's running
docker ps | grep postgres
```

**Using Local PostgreSQL:**
```bash
# Create database
createdb -U postgres octofy_users

# Update .env with your credentials
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=octofy_users
```

### Step 3: Configure Environment

Create or update your `.env` file:

```env
# Authentication (REQUIRED - CHANGE THESE!)
JWT_SECRET_KEY=<generate-a-secure-32-char-secret>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_DAYS=7

# PostgreSQL
POSTGRES_USER=octofy
POSTGRES_PASSWORD=***REMOVED***
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=octofy_users

# Legacy API key (for backward compatibility)
API_KEY=your-existing-api-key

# Other existing config...
LLM_API_KEY=sk-...
SQL_SERVER_CONNECTION_STRING=...
```

**Generate a secure JWT secret:**
```bash
# Option 1: OpenSSL (Linux/Mac)
openssl rand -hex 32

# Option 2: Python
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 4: Initialize Database

```bash
python scripts/init_user_db.py
```

**Expected output:**
```
Initializing user database...
PostgreSQL Host: localhost:5432
Database: octofy_users
✅ Database tables created successfully
================================================================================
DEFAULT ADMINISTRATOR ACCOUNT CREATED
================================================================================
Username: admin
Password: admin123
API Key: Xr8mK3pT9vL2nH5wQ4jC6fN8yU1sA7bV3xZ0gD9eM2kR5tY7
================================================================================
⚠️  WARNING: Change the default password immediately after first login!
================================================================================
✅ User database initialization complete!
```

### Step 5: Start Backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Look for these startup messages:**
```
INFO:     Initializing user database...
INFO:     User database initialized with 1 user(s)
INFO:     Checking Vector Database Schema Index...
```

---

## Testing the API

### Test 1: Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

**Expected response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "full_name": "System Administrator",
    "role": "admin",
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z",
    "last_login_at": "2024-01-01T12:00:00Z"
  }
}
```

**Save the `access_token` for next requests!**

### Test 2: Get Current User Info (Including API Key)

```bash
# Replace <TOKEN> with your access_token from login
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <TOKEN>"
```

**Expected response includes API key:**
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "api_key": "Xr8mK3pT9vL2nH5wQ4jC6fN8yU1sA7bV3xZ0gD9eM2kR5tY7",
  "role": "admin",
  ...
}
```

### Test 3: Create a New User (Admin Only)

```bash
curl -X POST http://localhost:8000/api/v1/admin/users \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "email": "john@example.com",
    "password": "secure_password",
    "full_name": "John Doe",
    "role": "user"
  }'
```

### Test 4: Test User API Key Authentication

```bash
# Use the API key instead of JWT token
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "X-API-Key: Xr8mK3pT9vL2nH5wQ4jC6fN8yU1sA7bV3xZ0gD9eM2kR5tY7"
```

### Test 5: Create a Conversation

```bash
curl -X POST http://localhost:8000/api/v1/conversations \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Conversation",
    "messages": [
      {
        "role": "user",
        "content": "Hello, how do I query sales data?",
        "timestamp": "2024-01-01T12:00:00Z"
      }
    ]
  }'
```

### Test 6: List Conversations

```bash
curl -X GET http://localhost:8000/api/v1/conversations \
  -H "Authorization: Bearer <TOKEN>"
```

---

## Common Issues

### Issue 1: PostgreSQL Connection Refused

**Error:**
```
sqlalchemy.exc.OperationalError: could not connect to server: Connection refused
```

**Solution:**
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# Start it if not running
docker-compose up -d postgres

# Check logs
docker-compose logs postgres
```

### Issue 2: JWT Token Invalid

**Error:**
```
401 Unauthorized: Invalid or missing authentication credentials
```

**Solution:**
- Check `JWT_SECRET_KEY` in `.env` matches the deployment
- Token may have expired (7 days) - login again
- Verify Authorization header format: `Bearer <token>`

### Issue 3: Default Admin Not Created

**Error:**
```
No users found but admin not created
```

**Solution:**
```bash
# Run init script manually
python scripts/init_user_db.py
```

### Issue 4: Import Errors

**Error:**
```
ImportError: cannot import name 'get_user_db' from 'app.core.user_database'
```

**Solution:**
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Verify Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

---

## Quick Reference

### Authentication Methods

| Method | Header | Use Case |
|--------|--------|----------|
| JWT Token | `Authorization: Bearer <token>` | Web frontend |
| User API Key | `X-API-Key: <user_api_key>` | Scripts/integrations |
| Legacy API Key | `X-API-Key: <system_api_key>` | Backward compatibility (deprecated) |

### User Roles

| Role | Permissions |
|------|-------------|
| **admin** | Full access - can manage users, access admin panel, manage all data |
| **user** | Chat access - can use chat, manage own profile and conversations |

### Important Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/login` | POST | Login with username/password |
| `/api/v1/auth/me` | GET | Get current user info + API key |
| `/api/v1/users/me` | PUT | Update own profile |
| `/api/v1/users/me/regenerate-api-key` | POST | Regenerate API key |
| `/api/v1/conversations` | GET | List conversations |
| `/api/v1/conversations` | POST | Create conversation |
| `/api/v1/admin/users` | GET | List all users (admin) |
| `/api/v1/admin/users` | POST | Create user (admin) |

---

## Security Checklist

- [ ] Changed default admin password
- [ ] Generated secure JWT_SECRET_KEY (32+ chars)
- [ ] Updated POSTGRES_PASSWORD in production
- [ ] Enabled HTTPS for production deployment
- [ ] Reviewed user list and removed test accounts
- [ ] Documented API keys in secure password manager
- [ ] Set up database backups for PostgreSQL
- [ ] Configured firewall rules for PostgreSQL port (5432)

---

## Next Steps

1. **Change the default admin password**
   ```bash
   curl -X PUT http://localhost:8000/api/v1/users/me \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"password": "your-strong-password"}'
   ```

2. **Create user accounts for your team**
   - Use `/api/v1/admin/users` endpoint
   - Or build a frontend UI for user management

3. **Test conversation history**
   - Create, update, and delete conversations
   - Verify they persist across sessions

4. **Migrate existing clients**
   - Update scripts to use JWT tokens or user API keys
   - Monitor logs for legacy API key usage
   - Plan deprecation timeline

5. **Build frontend authentication**
   - Login page with JWT token storage
   - Protected routes
   - User profile page
   - Conversation history sidebar

---

## Documentation

For complete documentation, see:
- **[USER_MANAGEMENT.md](USER_MANAGEMENT.md)** - Full API reference and architecture
- **[CONTEXT.md](CONTEXT.md)** - Updated project overview
- **[BACKEND_API.md](BACKEND_API.md)** - Complete API documentation

---

## Support

Having issues? Check the logs:
```bash
# Backend logs
tail -f logs/app.log

# PostgreSQL logs
docker-compose logs -f postgres

# Check database connection
python -c "from app.core.user_database import engine; print(engine.execute('SELECT 1').fetchone())"
```
