# Backend API Documentation

FastAPI backend for the Octofy AI Agent, focused on natural language to SQL generation, code generation/execution, schema discovery, and admin governance workflows.

---

## Backend Feature Summary

- Query discovery and context synthesis from vector store metadata.
- Streaming generation for SQL, Python, R, SAS, and code-advisor responses (SSE).
- SQL and Python execution endpoints with auto-fix retry loops.
- Admin schema, few-shot, value-index, and vector-store backup operations.
- Multi-source data-source and schema-tree management APIs.
- Contribution submission + admin approval workflow.
- User authentication, user management, user activity analytics.
- Conversation persistence APIs for chat history.

---

## Technology Stack

| Technology | Purpose |
|------------|---------|
| FastAPI | Web framework |
| SQLAlchemy + pyodbc | SQL Server connectivity |
| Milvus | Vector search / indexing |
| OpenAI + LiteLLM | LLM + embeddings |
| Pydantic | Validation and response schemas |

---

## Base URL, OpenAPI, and Health

| Item | Value |
|------|-------|
| Base URL | `/api/v1` |
| Health Check | `GET /` -> `{"message":"Database AI Agent API is running"}` |
| OpenAPI Spec | `GET /api/v1/openapi.json` |
| Swagger UI | `http://localhost:8000/docs` |

---

## Authentication Model

This API uses API-key based authentication in `X-API-Key`.

```http
X-API-Key: <user-or-admin-api-key>
```

### Auth Rules

- `POST /api/v1/auth/login` is public (username/password login).
- Most user endpoints require a valid user API key.
- Admin endpoints require an active admin API key.
- `GET /api/v1/admin/ingest-progress` is currently open (no auth dependency in route).

### Common Error Responses

| Status | Response |
|--------|----------|
| 400 | `{"detail": "Bad request"}` |
| 401 | `{"detail": "Invalid or missing API key"}` |
| 403 | `{"detail": "Insufficient permissions"}` |
| 404 | `{"detail": "Resource not found"}` |
| 500 | `{"detail": "Internal server error"}` |

---

## Core Endpoints

### Discovery

| Endpoint | Method | Notes |
|----------|--------|-------|
| `/api/v1/discovery` | POST | Semantic discovery (tables, similar queries, glossary terms) |
| `/api/v1/test` | POST | Simple authenticated test endpoint |

---

### Generation (Streaming SSE)

All endpoints stream progress/status/result as `text/event-stream`.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/generate-sql` | POST | Generate T-SQL |
| `/api/v1/generate-python` | POST | Generate Python code |
| `/api/v1/generate-r` | POST | Generate R code |
| `/api/v1/generate-sas` | POST | Generate SAS code |
| `/api/v1/code-advisor` | POST | Streaming code advisor (rate-limited) |

Typical SSE events:
- `status` (step updates)
- `result` (final payload)
- `done` (stream completion)
- `error` (error payload)

---

### Execution and Summarization

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/execute-sql` | POST | Execute SQL with retry/auto-fix support |
| `/api/v1/execute-python` | POST | Execute Python with retry/auto-fix support |
| `/api/v1/planning-summary` | POST | Generate planning context summary |
| `/api/v1/summarize-results` | POST | Natural-language summary of result preview |

Execution endpoints support richer responses including profiling, insights, recommendations, `auto_fixed`, and retry metadata.

---

### Schema Lookup

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/schema/{object_name}` | GET | Returns schema details for a specific object |

---

## User and Conversation APIs

### Authentication and Profile

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/auth/login` | POST | Login with username/password, returns API key as `access_token` |
| `/api/v1/auth/me` | GET | Current user details |
| `/api/v1/users/me` | PUT | Update current user profile |
| `/api/v1/users/me/regenerate-api-key` | POST | Regenerate current user API key |

### Admin User Management

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/admin/users` | GET | List users |
| `/api/v1/admin/users/{user_id}` | GET | User details |
| `/api/v1/admin/users` | POST | Create user |
| `/api/v1/admin/users/{user_id}` | PUT | Update user |
| `/api/v1/admin/users/{user_id}` | DELETE | Delete user |
| `/api/v1/admin/users/{user_id}/regenerate-api-key` | POST | Regenerate user API key |
| `/api/v1/admin/users/{user_id}/stats` | GET | User statistics |
| `/api/v1/admin/users/{user_id}/activities` | GET | User activity log |
| `/api/v1/admin/users/overview` | GET | System-wide user overview |

### Conversations

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/conversations` | GET | List current user conversations |
| `/api/v1/conversations/{conversation_id}` | GET | Get conversation |
| `/api/v1/conversations` | POST | Create conversation |
| `/api/v1/conversations/{conversation_id}` | PUT | Update conversation |
| `/api/v1/conversations/{conversation_id}` | DELETE | Delete conversation |

---

## Contributions

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/contributions` | POST | Submit contribution |
| `/api/v1/admin/contributions` | GET | List pending contributions (admin) |
| `/api/v1/admin/contributions/approve` | POST | Approve contribution (admin) |
| `/api/v1/admin/contributions/{contribution_id}` | DELETE | Reject contribution (admin) |

---

## Admin APIs

All routes below are prefixed with `/api/v1/admin`.

### Schema Management

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/schema/status` | GET | Indexed schema status |
| `/schema/sync` | POST | Sync one table |
| `/schema/sync-full` | POST | Full schema sync |
| `/schema/batch-sync` | POST | Batch table sync |
| `/schema/description` | PUT | Update description |
| `/schema` | DELETE | Delete schema |
| `/schema/export` | GET | Export schema index |
| `/schema/template` | GET | Download schema template |
| `/schema/clear` | POST | Clear schema index |
| `/ingest-schemas` | POST | Ingest schema Excel |

### Object-Level Schema Library

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/object` | POST | Add object metadata |
| `/object/sync` | POST | Sync specific object |
| `/object` | DELETE | Delete object metadata |
| `/object/discover` | POST | Discover objects |
| `/enhance-schema` | POST | AI-assisted schema enhancement |

### Few-Shot (Knowledge Base)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/fewshots` | GET | List few-shots |
| `/fewshots` | POST | Add few-shot |
| `/fewshots/{item_id}` | DELETE | Delete few-shot |
| `/fewshots/export` | GET | Export few-shots |
| `/ingest-fewshots` | POST | Ingest few-shots from file |

### Value Index

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/values` | GET | List value-index items |
| `/values/search` | GET | Search values |
| `/values/{item_id}` | DELETE | Delete value item |
| `/values/clear` | POST | Clear values |
| `/values/template` | GET | Download values template |
| `/values/export` | GET | Export values |
| `/ingest-values` | POST | Ingest values file (Excel/CSV) |
| `/ingest-progress` | GET | SSE ingest progress |

### Settings and Connectivity

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/settings` | GET | Get settings |
| `/settings` | PUT | Update settings |
| `/api-key` | GET | Read env API key |
| `/api-key` | POST | Set env API key |
| `/test-connection` | POST | Test DB connection |
| `/verify-settings` | POST | Verify DB/LLM/Milvus |
| `/models` | GET | List available models |
| `/fetch-models` | POST | Fetch models from endpoint |
| `/build-connection-string` | POST | Build DB connection string |

### Multi-Source Management

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/data-sources` | GET | List data sources |
| `/data-sources` | POST | Add data source |
| `/data-sources/{source_id}` | GET | Get data source |
| `/data-sources/{source_id}` | PUT | Update data source |
| `/data-sources/{source_id}` | DELETE | Delete data source |
| `/data-sources/{source_id}/scan` | POST | Trigger source scan |
| `/data-sources/{source_id}/scan-status` | GET | Scan status |
| `/data-sources/{source_id}/test` | POST | Connection test wrapper |
| `/data-sources/{source_id}/enable` | POST | Enable/disable source |
| `/data-sources/{source_id}/set-primary` | POST | Set primary source |
| `/data-sources/{source_id}/exclude-objects` | POST | Upload exclusion list |
| `/data-sources/{source_id}/exclude-objects` | GET | Get exclusion list |
| `/data-sources/{source_id}/exclude-objects` | DELETE | Delete exclusion list |

Notes:
- `GET /api/v1/admin/data-sources` accepts any valid user `X-API-Key`.
- Use `data_sources[*].source_id` as the data source id and `data_sources[*].friendly_name` as the data source name.

#### Data Source Resolution

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/data-sources/resolve` | GET | Resolve connection details to source_id |

**Query Parameters:**

For SQL Server sources:
- `server`: Server name (required with database)
- `database`: Database name (required with server)

For Excel/File sources:
- `file_path`: Full path to file

**Example Request (SQL Server):**
```bash
GET /api/v1/data-sources/resolve?server=SQLSERVER01&database=Northwind
```

**Example Response:**
```json
{
  "source_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "name": "Northwind Production",
  "type": "SQL Server",
  "server": "SQLSERVER01",
  "database": "Northwind",
  "file_path": null,
  "status": "active",
  "object_count": 245
}
```

**Example Request (Excel):**
```bash
GET /api/v1/data-sources/resolve?file_path=/data/sales.xlsx
```

**Example Response:**
```json
{
  "source_id": "e5f6a7b8-c9d0-1234-abcd-ef1234567890",
  "name": "Sales Data",
  "type": "Excel",
  "server": null,
  "database": null,
  "file_path": "/data/sales.xlsx",
  "status": "active",
  "object_count": 12
}
```

**Error Responses:**
- `400`: Invalid parameter combination
  - Only `server` provided (missing `database`)
  - Only `database` provided (missing `server`)
  - Mixed SQL Server and file parameters
  - No parameters provided
- `404`: Data source not found

**Usage Pattern:**
```bash
# Step 1: Resolve SQL Server data source to ID
RESOLVED=$(curl -s "http://localhost:8000/api/v1/data-sources/resolve?server=MyServer&database=MyDB" \
  -H "X-API-Key: admin-key" | jq -r '.source_id')

# Step 2: Use source_id in discovery
curl -X POST http://localhost:8000/api/v1/discovery \
  -H "X-API-Key: user-key" \
  -d "{\"query\": \"show customers\", \"source_id\": \"$RESOLVED\"}"

# Step 3: Use source_id in generate-sql
curl -X POST http://localhost:8000/api/v1/generate-sql \
  -H "X-API-Key: user-key" \
  -d "{\"query\": \"show top 10 customers\", \"source_id\": \"$RESOLVED\"}"
```

**Notes:**
- Server and database matching is case-insensitive
- File path matching is case-sensitive (filesystem dependent)
- Only active (non-deleted) data sources are returned
- Requires admin authentication
- Object count reflects number of tables/views/procedures indexed in vector store

### Schema Tree Navigation

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/schema-tree` | GET | Full tree across sources |
| `/schema-tree/{source_id}` | GET | Tree for one source |
| `/schema-tree/{source_id}/schemas` | GET | List source schemas |
| `/schema-tree/{source_id}/objects` | GET | List objects with filters |
| `/schema-tree/{source_id}/discover` | POST | DB introspection discovery |

### Skills Admin Utilities

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/skills/data-sources` | GET/POST | List or create skill data sources |
| `/skills/data-sources/{data_source_name}` | PUT/DELETE | Update/delete skill data source |
| `/skills/data-groups` | GET/POST/PUT/DELETE | Manage data groups |
| `/skills/tables` | GET/POST/PUT/DELETE | Manage tables |
| `/skills/tables/by-path` | GET | Fetch table by path |
| `/skills/raw-markdown` | GET/PUT | Read/update raw markdown |
| `/skills/sync-schema-markdown` | POST | Sync schema markdown |
| `/skills/folder-tree` | GET | Skills folder tree |
| `/skills/search` | GET | Skills search |
| `/skills/objects` | GET | List skill objects |
| `/skills/objects/by-name` | GET | Get object by name |
| `/skills/statistics` | GET | Skills statistics |
| `/skills/regenerate-indices` | POST | Rebuild skill indexes |

### Backup

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/vector-store/backup` | GET | Download vector-store backup JSON |

---

## Notes on Request Models

### `GenerateSQLRequest`
Common fields used by generation endpoints:
- `query` (required)
- `context`, `previousSQL`, `queryHistory`
- `forceGeneral`, `queryMode`
- `table_override`, `chart_type_override`

### `ExecuteSQLRequest`
Supports execution controls like:
- `sql`
- `context`
- `timeout_seconds`, `max_rows`
- `enable_profiling`
- `chart_type_override`, axis preservation fields
- `source_id` (multi-source execution)

### `ExecutePythonRequest`
Supports:
- `code`
- optional execution context
- profiling and chart override controls

---

## Development / Testing Quick Commands

```bash
# Run backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests
python -m pytest tests/
```

---

## Change Log (Doc Sync)

This document has been updated to reflect currently implemented routes, including:
- User/auth and conversation APIs.
- Multi-source data-source and schema-tree APIs.
- `execute-sql`, `planning-summary`, and `code-advisor` generation additions.
- Updated health-check message and authentication behavior notes.
