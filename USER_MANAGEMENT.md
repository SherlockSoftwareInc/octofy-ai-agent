# User Management System

> Complete authentication, authorization, and conversation history management for Octofy AI Agent.

---

## Overview

The User Management System adds full multi-user support to Octofy AI Agent with:

- **Authentication**: Username/password login with JWT tokens (7-day expiry)
- **Authorization**: Role-based access control (Admin vs User)
- **User Profiles**: Auto-generated API keys for programmatic access
- **Conversation History**: PostgreSQL-backed conversation storage synced across devices
- **Backward Compatibility**: Legacy system API key still supported during migration

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Auth)                      │
│  Login Page → JWT Token → Protected Routes → Chat Interface    │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP (Bearer Token or API Key)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                          │
│  /api/v1/auth/*   /api/v1/users/*   /api/v1/conversations/*   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  PostgreSQL (Port 5432) │
                    │  - users              │
                    │  - conversations      │
                    └──────────────────────┘
```

---

## Database Schema

### Users Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| username | VARCHAR(100) | Unique username |
| email | VARCHAR(255) | Email address (optional) |
| hashed_password | VARCHAR(255) | Bcrypt hashed password |
| full_name | VARCHAR(255) | Full name (optional) |
| role | VARCHAR(20) | 'admin' or 'user' |
| is_active | BOOLEAN | Account status |
| api_key | VARCHAR(64) | Auto-generated API key |
| created_at | TIMESTAMP | Account creation time |
| updated_at | TIMESTAMP | Last update time |
| last_login_at | TIMESTAMP | Last successful login |

### Conversations Table

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| user_id | INTEGER | Foreign key to users |
| title | VARCHAR(255) | Conversation title |
| messages | JSON | Array of message objects |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update time |

**Message JSON Structure:**
```json
{
  "role": "user" | "assistant" | "system",
  "content": "message text",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

New dependencies:
- `psycopg2-binary`: PostgreSQL adapter
- `python-jose[cryptography]`: JWT token handling
- `passlib[bcrypt]`: Password hashing

### 2. Start PostgreSQL

**Option A: Docker Compose (Recommended)**
```bash
docker-compose up -d postgres
```

**Option B: Local PostgreSQL**
```bash
# Install PostgreSQL 15+
# Create database
createdb -U postgres octofy_users
```

### 3. Configure Environment

Update `.env` with PostgreSQL credentials:
```env
# PostgreSQL Configuration
POSTGRES_USER=octofy
POSTGRES_PASSWORD=octofy_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=octofy_users

# JWT Configuration (CHANGE THESE!)
JWT_SECRET_KEY=your-super-secret-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_DAYS=7

# Legacy API key (for backward compatibility)
API_KEY=your-existing-api-key
```

**Generate a secure JWT secret:**
```bash
# Linux/Mac
openssl rand -hex 32

# Python
python -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Initialize Database

```bash
# Create tables and default admin account
python scripts/init_user_db.py
```

**Default Admin Credentials:**
- Username: `admin`
- Password: `admin123`
- **⚠️ CHANGE PASSWORD AFTER FIRST LOGIN!**

### 5. Start Backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend will automatically:
1. Connect to PostgreSQL
2. Create tables if they don't exist
3. Create default admin if no users exist

---

## API Reference

### Authentication

#### Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

**Response:**
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

#### Get Current User
```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

**Response includes API key:**
```json
{
  "id": 1,
  "username": "admin",
  "api_key": "Xr8mK3pT9vL2nH5wQ4jC6fN8yU1sA7bV3xZ0gD9eM2kR5tY7",
  ...
}
```

### User Management (Admin Only)

#### List Users
```http
GET /api/v1/admin/users?skip=0&limit=100
Authorization: Bearer <admin_token>
```

#### Create User
```http
POST /api/v1/admin/users
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "secure_password",
  "full_name": "John Doe",
  "role": "user"
}
```

#### Update User
```http
PUT /api/v1/admin/users/{user_id}
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "email": "newemail@example.com",
  "role": "admin",
  "is_active": false
}
```

#### Delete User
```http
DELETE /api/v1/admin/users/{user_id}
Authorization: Bearer <admin_token>
```

### User Profile

#### Update Own Profile
```http
PUT /api/v1/users/me
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "email": "newemail@example.com",
  "full_name": "Updated Name",
  "password": "new_password"
}
```

#### Regenerate API Key
```http
POST /api/v1/users/me/regenerate-api-key
Authorization: Bearer <access_token>
```

### Conversations

#### List Conversations
```http
GET /api/v1/conversations?skip=0&limit=50
Authorization: Bearer <access_token>
```

#### Get Conversation
```http
GET /api/v1/conversations/{conversation_id}
Authorization: Bearer <access_token>
```

#### Create Conversation
```http
POST /api/v1/conversations
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "title": "My Chat Session",
  "messages": [
    {
      "role": "user",
      "content": "Hello!",
      "timestamp": "2024-01-01T12:00:00Z"
    }
  ]
}
```

#### Update Conversation
```http
PUT /api/v1/conversations/{conversation_id}
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "title": "Updated Title",
  "messages": [...]
}
```

#### Delete Conversation
```http
DELETE /api/v1/conversations/{conversation_id}
Authorization: Bearer <access_token>
```

---

## Authentication Methods

The system supports **three** authentication methods:

### 1. JWT Bearer Token (Recommended for Web)
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

- Used by frontend after login
- Expires after 7 days (configurable)
- Contains user ID, username, and role

### 2. User API Key (For Scripts/Integrations)
```http
X-API-Key: Xr8mK3pT9vL2nH5wQ4jC6fN8yU1sA7bV3xZ0gD9eM2kR5tY7
```

- Auto-generated per user
- Never expires (until regenerated)
- Can be regenerated anytime

### 3. Legacy System API Key (Deprecated)
```http
X-API-Key: your-old-system-api-key
```

- Supported for backward compatibility
- No user context (logs warning)
- **Migrate to user-based auth ASAP**

---

## Role-Based Access Control

### Admin Role
- Full access to all endpoints
- Can create/update/delete users
- Can manage all conversations
- Can access admin panel
- Can view system settings

### User Role
- Can chat and generate queries
- Can manage own profile
- Can manage own conversations
- **Cannot** access admin endpoints
- **Cannot** manage other users

---

## Security Best Practices

### 1. Change Default Credentials
```bash
# After first deployment
curl -X PUT http://localhost:8000/api/v1/users/me \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"password": "strong-new-password-here"}'
```

### 2. Use Strong JWT Secret
```bash
# Generate 32-byte random secret
openssl rand -hex 32
```

### 3. Enable HTTPS in Production
```python
# main.py
app.add_middleware(
    HTTPSRedirectMiddleware
)
```

### 4. Rotate API Keys Regularly
- Users can regenerate their API keys anytime
- Old key becomes invalid immediately
- Update all applications using the key

### 5. Monitor Failed Login Attempts
Check logs for suspicious activity:
```bash
grep "401" logs/app.log | grep "login"
```

---

## Migration Guide

### From Single API Key to User Accounts

**Phase 1: Deploy (Backward Compatible)**
1. Deploy new version with user management
2. Legacy API key still works
3. No disruption to existing clients

**Phase 2: Create User Accounts**
1. Admin logs in with default credentials
2. Creates user accounts for each team member
3. Distributes credentials or invitation links

**Phase 3: Migrate Clients**
1. Update clients to use JWT tokens or user API keys
2. Test thoroughly
3. Monitor for any legacy API key usage (check logs)

**Phase 4: Deprecate Legacy Key**
1. Disable legacy API key in config
2. All clients now using user-based auth

---

## Troubleshooting

### PostgreSQL Connection Failed
```
Error: could not connect to server: Connection refused
```

**Solution:**
- Verify PostgreSQL is running: `docker ps` or `pg_isready`
- Check credentials in `.env`
- Check firewall/network settings

### Default Admin Not Created
```
User database initialized with 0 user(s) but admin not created
```

**Solution:**
```bash
python scripts/init_user_db.py
```

### JWT Token Invalid
```
401 Unauthorized: Invalid or missing authentication credentials
```

**Possible causes:**
- Token expired (7 days)
- JWT_SECRET_KEY changed (invalidates all tokens)
- Token malformed

**Solution:**
- Login again to get new token
- Check JWT_SECRET_KEY in `.env` matches deployment

### API Key Not Working
```
401 Unauthorized: Invalid API key
```

**Solution:**
- Verify API key is correct (check `/api/v1/auth/me`)
- Check user is active: `is_active: true`
- Regenerate API key if needed

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | octofy | PostgreSQL username |
| `POSTGRES_PASSWORD` | octofy_password | PostgreSQL password |
| `POSTGRES_HOST` | localhost | PostgreSQL host |
| `POSTGRES_PORT` | 5432 | PostgreSQL port |
| `POSTGRES_DB` | octofy_users | PostgreSQL database name |
| `JWT_SECRET_KEY` | (required) | Secret key for JWT signing |
| `JWT_ALGORITHM` | HS256 | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_DAYS` | 7 | Token expiration in days |
| `API_KEY` | (required) | Legacy system API key |

---

## Future Enhancements

- [ ] Email verification for new users
- [ ] Password reset via email
- [ ] OAuth2 integration (Google, Microsoft, GitHub)
- [ ] Two-factor authentication (2FA)
- [ ] API key expiration dates
- [ ] Rate limiting per user
- [ ] Audit log for admin actions
- [ ] User groups and permissions
- [ ] Session management (revoke tokens)
- [ ] LDAP/Active Directory integration

---

## Support

For issues or questions about user management:
- Check logs: `logs/app.log`
- Review this documentation
- Check PostgreSQL status: `docker-compose logs postgres`
- Verify configuration: `.env` and `config.py`
