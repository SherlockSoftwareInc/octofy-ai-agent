# Backend API Documentation

> FastAPI backend for the Octofy AI Agent - Natural Language to SQL generation service.

---

## Overview

The backend provides RESTful APIs and Server-Sent Events (SSE) for:
- Natural language to SQL/R/SAS/Python code generation
- Schema discovery and semantic search
- Admin management for schemas, knowledge base, and value index
- User contribution submission and review

---

## Technology Stack

| Technology | Purpose |
|------------|---------|
| **FastAPI** | Web framework |
| **SQLAlchemy + pyodbc** | SQL Server connectivity |
| **Milvus** | Vector database |
| **OpenAI** | LLM and embeddings |
| **LiteLLM** | Multi-provider LLM support |
| **Pydantic** | Data validation |

---

## Project Structure

```
app/
├── api/endpoints/
│   ├── discovery.py      # Schema discovery
│   ├── generation.py     # SQL/code generation (SSE)
│   ├── schema.py         # Schema lookup
│   ├── admin.py          # Admin operations
│   ├── settings.py       # Configuration
│   ├── contributions.py  # User contributions
│   └── summarize.py      # Result summarization
├── core/
│   ├── config.py         # Settings (env vars)
│   ├── database.py       # SQLAlchemy engine
│   └── auth.py           # API key validation
├── models/
│   └── schemas.py        # Pydantic models
├── services/
│   ├── generation_service.py   # SQL generation logic
│   ├── discovery_service.py    # Context discovery
│   ├── llm_service.py          # LLM interactions
│   ├── validation_service.py   # SQL validation
│   ├── vector_store.py         # Milvus operations
│   ├── ingest_service.py       # Schema ingestion
│   ├── execution_service.py    # Python execution
│   ├── visualization_service.py # Chart recommendations
│   ├── profiling_service.py    # Data profiling
│   ├── insight_service.py      # AI insights
│   └── settings_service.py     # Settings management
└── utils/
    └── logging_utils.py        # LLM interaction logging
```

---

## Base URL and Authentication

| Item | Value |
|------|-------|
| **Base URL** | `/api/v1` |
| **Health Check** | `GET /` → `{"message":"Octofy AI Agent API is running"}` |
| **OpenAPI Spec** | `GET /api/v1/openapi.json` |
| **Swagger UI** | `http://localhost:8000/docs` |

### Authentication

All endpoints require API key authentication (unless noted):

```http
X-API-Key: <your-api-key>
```

Configure in `.env` or `app/core/config.py`:
```env
API_KEY=your-secure-api-key
```

### Error Responses

| Status | Response |
|--------|----------|
| `400` | `{"detail": "Bad request message"}` |
| `401` | `{"detail": "Invalid or missing API key"}` |
| `404` | `{"detail": "Resource not found"}` |
| `500` | `{"detail": "Internal server error"}` |

---

## Core API Endpoints

### Discovery

Find relevant tables, similar queries, and glossary terms for a natural language question.

```http
POST /api/v1/discovery
```

**Request Body:**
```json
{
  "query": "Show me top customers by revenue",
  "top_k": 5
}
```

**Response:**
```json
{
  "query": "Show me top customers by revenue",
  "reasoning": "Identified 3 relevant tables and 2 similar queries.",
  "context": {
    "relevant_tables": [
      {
        "schema_name": "dbo",
        "table_name": "Customers",
        "table_type": "table",
        "description": "# Table: [dbo].[Customers]...",
        "columns": [
          {"name": "CustomerID", "data_type": "NCHAR(5)", "description": "Primary key"}
        ]
      }
    ],
    "similar_queries": [
      {"question": "Top 10 customers", "sql": "SELECT TOP 10..."}
    ],
    "glossary_terms": {}
  }
}
```

---

### SQL/Code Generation (Streaming SSE)

Generate SQL or code with real-time status updates via Server-Sent Events.

#### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/generate-sql` | T-SQL generation |
| `POST /api/v1/generate-r` | R code generation |
| `POST /api/v1/generate-sas` | SAS code generation |
| `POST /api/v1/generate-python` | Python code generation |

**Request Body (`GenerateSQLRequest`):**
```json
{
  "query": "Top 10 customers by revenue",
  "context": null,
  "previousSQL": null,
  "queryHistory": null,
  "forceGeneral": false,
  "queryMode": "generate",
  "table_override": ["dbo.Customers", "dbo.Orders"],
  "chart_type_override": "column"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `query` | string | Natural language question (required) |
| `context` | DiscoveryContext | Pre-computed context (optional) |
| `previousSQL` | string | Previous SQL for refinement (optional) |
| `queryHistory` | string | Conversation history (optional) |
| `forceGeneral` | boolean | Skip classification, use general LLM (default: false) |
| `queryMode` | string | `"generate"` or `"search"` (default: generate) |
| `table_override` | string[] | Lock context to specific tables (optional) |
| `chart_type_override` | string | Requested chart type (optional) |

**SSE Response Events:**

```
data: {"step_id":1,"message":"Analyzing query...","type":"status","timestamp":1234567890.0}

data: {"step_id":2,"message":"Discovering relevant schemas...","type":"status","timestamp":1234567891.0}

data: {"type":"result","payload":{"sql":"SELECT TOP 10...","explanation":"...","query_type":"database"}}
```

**Event Types:**

| Type | Description |
|------|-------------|
| `status` | Progress update with step info |
| `result` | Final generated SQL/code |
| `error` | Error message |

**Example cURL:**
```bash
curl -N -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"query":"Top 10 customers by revenue"}' \
  http://localhost:8000/api/v1/generate-sql
```

---

### Schema Lookup

Get schema details for a specific table.

```http
GET /api/v1/schema/{object_name}
```

**Parameters:**
- `object_name`: Format `schema.table` (brackets stripped automatically)

**Response (`TableSchema`):**
```json
{
  "schema_name": "dbo",
  "table_name": "Customers",
  "table_type": "table",
  "description": "# Table: [dbo].[Customers]...",
  "columns": [
    {"name": "CustomerID", "data_type": "NCHAR(5)", "description": "Primary key"}
  ]
}
```

---

### Python Execution

Execute generated Python code and get results with visualization recommendations.

```http
POST /api/v1/execute-python
```

**Request Body:**
```json
{
  "code": "import pandas as pd\ndf = pd.read_sql(...)",
  "context": {"user_query": "Top customers"},
  "chart_type_override": "column"
}
```

**Response (`ExecutePythonResponse`):**
```json
{
  "success": true,
  "output": null,
  "error": null,
  "results": [
    {
      "name": "df",
      "type": "dataframe",
      "data": {"columns": ["Name", "Revenue"], "data": [...]},
      "rows": 10,
      "columns": ["Name", "Revenue"],
      "viz_config": {
        "category": "2d_data",
        "allowed_charts": ["column", "pie"],
        "message": "Recommended for categorical comparison"
      }
    }
  ],
  "recommendation": {
    "chart_type": "column",
    "x_axis": "Name",
    "y_axis": ["Revenue"],
    "title": "Top Customers by Revenue"
  },
  "execution_time": 0.45,
  "data_profile": {...},
  "insights": [...],
  "auto_fixed": false,
  "fix_attempt": 1
}
```

---

### Result Summarization

Generate natural language summary of query results.

```http
POST /api/v1/summarize-results
```

**Request Body:**
```json
{
  "user_request": "Top customers by revenue",
  "data_preview": [{"Name": "Customer A", "Revenue": 50000}],
  "chart_type": "column"
}
```

**Response:**
```json
{
  "summary": "The top customer is Customer A with $50,000 in revenue..."
}
```

---

## Admin Endpoints

All admin endpoints are prefixed with `/api/v1/admin/` and require authentication.

### Schema Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/schema/status` | GET | List all schemas with sync status |
| `/admin/schema/sync` | POST | Sync single table (`?schema=dbo&table=Customers`) |
| `/admin/schema/sync-full` | POST | Sync all schemas from database |
| `/admin/schema/batch-sync` | POST | Sync multiple tables |
| `/admin/schema/description` | PUT | Update table description |
| `/admin/schema` | DELETE | Delete schema from index |
| `/admin/schema/export` | GET | Export schemas to Excel |
| `/admin/schema/template` | GET | Download Excel template |
| `/admin/schema/clear` | POST | Clear all schemas |
| `/admin/ingest-schemas` | POST | Import schemas from Excel |

**Batch Sync Request:**
```json
{
  "table_names": ["dbo.Customers", "Orders", "Products"]
}
```

**Batch Sync Response:**
```json
{
  "total": 3,
  "successful": 3,
  "failed": 0,
  "results": [
    {"table_name": "Customers", "schema_name": "dbo", "success": true, "message": "Synced"}
  ]
}
```

---

### Knowledge Base (Few-Shot Examples)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/fewshots` | GET | List all examples |
| `/admin/fewshots` | POST | Add new example |
| `/admin/fewshots/{id}` | DELETE | Delete example |
| `/admin/fewshots/export` | GET | Export to Excel |
| `/admin/ingest-fewshots` | POST | Import from Excel |

**FewShotItem:**
```json
{
  "id": "12345",
  "question": "Top 10 customers by revenue",
  "sql_query": "SELECT TOP 10 c.CustomerName, SUM(o.Total) AS Revenue...",
  "knowledge_type": "sql_query",
  "verified": true
}
```

**Knowledge Types:** `sql_query`, `r_code`, `sas_code`, `general`

---

### Value Index

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/values` | GET | List all indexed values |
| `/admin/values/search` | GET | Search values (`?query=Canada&top_k=50`) |
| `/admin/values/{id}` | DELETE | Delete value |
| `/admin/values/clear` | POST | Clear all values |
| `/admin/values/export` | GET | Export to Excel |
| `/admin/values/template` | GET | Download Excel template |
| `/admin/ingest-values` | POST | Import from Excel/CSV |

**Value Index Item:**
```json
{
  "id": "67890",
  "value": "Canada",
  "schema_name": "dbo",
  "table_name": "Customers",
  "column_name": "Country"
}
```

---

### Contributions

Public endpoint for user submissions, plus admin review.

**Submit Contribution:**
```http
POST /api/v1/contributions
```

```json
{
  "question": "How many orders per country?",
  "sql_query": "SELECT Country, COUNT(*) FROM Orders GROUP BY Country",
  "knowledge_type": "sql_query",
  "user_id": "user123"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Contribution submitted for review",
  "contribution_id": "98765",
  "similarity_warning": true,
  "similarity_score": 0.85
}
```

**Admin Endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/contributions` | GET | List pending contributions |
| `/admin/contributions/approve` | POST | Approve and move to knowledge base |
| `/admin/contributions/{id}` | DELETE | Reject contribution |

---

### Settings & Connectivity

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/settings` | GET | Get current settings (secrets masked) |
| `/admin/settings` | PUT | Update settings |
| `/admin/test-connection` | POST | Test database connection |
| `/admin/verify-settings` | POST | Verify all connections |
| `/admin/models` | GET | List available LLM models |
| `/admin/fetch-models` | POST | Fetch models from endpoint |
| `/admin/build-connection-string` | POST | Build connection string |

**Connection Test Request:**
```json
{
  "driver": "ODBC Driver 17 for SQL Server",
  "server": "localhost",
  "database": "Northwind",
  "auth_type": "sql",
  "username": "sa",
  "password": "password123",
  "trust_server_certificate": true
}
```

**Verify Settings Response:**
```json
{
  "db_connected": true,
  "db_message": "Connected to Northwind",
  "llm_connected": true,
  "llm_message": "GPT-4o available",
  "milvus_connected": true,
  "milvus_message": "Connected to Milvus at localhost:19530"
}
```

---

### Vector Store Backup

```http
GET /api/v1/admin/vector-store/backup
```

Downloads a JSON backup of all vector store collections.

---

### Ingest Progress (SSE)

Monitor bulk import progress in real-time:

```http
GET /api/v1/admin/ingest-progress
```

**No authentication required.**

**SSE Events:**
```
data: {"current":0,"total":100,"percentage":0,"status":"processing"}
data: {"current":50,"total":100,"percentage":50,"status":"processing"}
data: {"current":100,"total":100,"percentage":100,"status":"complete"}
```

---

## Data Models

### TableSchema
```json
{
  "schema_name": "string",
  "table_name": "string",
  "table_type": "table | view",
  "description": "string (Markdown)",
  "columns": [ColumnInfo]
}
```

### ColumnInfo
```json
{
  "name": "string",
  "data_type": "string",
  "description": "string | null"
}
```

### GenerateSQLResponse
```json
{
  "sql": "string",
  "explanation": "string | null",
  "query_type": "database | general | uncertain | search",
  "context_text": "string | null",
  "context_history": ["string"],
  "objects": [SearchObject]
}
```

### AgentSettings
```json
{
  "llm_config": {
    "llm_model": "gpt-4o",
    "temperature": 0.0,
    "llm_endpoint": "https://api.openai.com/v1",
    "llm_api_key": "sk-..."
  },
  "embedding_config": {
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "api_key": "sk-...",
    "model": "text-embedding-3-small",
    "dimensions": 1536
  },
  "vector_config": {
    "provider": "milvus",
    "host": "localhost",
    "port": "19530"
  },
  "app_meta": {
    "app_name": "Octofy AI Agent",
    "version": "1.0.0",
    "project_name": "Octofy AI Agent"
  }
}
```

**Note**: Database connection info is NOT in settings. Data sources are defined in `skills/data-sources/*/data-source.md` files.

---

## Services Architecture

### Generation Flow

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│         generation_service.py       │
│  1. Query Analysis & Intent         │
│  2. Multi-Source Discovery          │
│  3. Context Expansion               │
│  4. Schema Validation               │
│  5. Iterative SQL Generation (5x)   │
└──────────────┬──────────────────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│ LLM    │ │ Milvus │ │ SQL    │
│ Service│ │ Vector │ │ Server │
│        │ │ Store  │ │        │
└────────┘ └────────┘ └────────┘
```

### Key Services

| Service | Purpose |
|---------|---------|
| `generation_service.py` | Main SQL generation orchestration |
| `discovery_service.py` | Schema and context discovery |
| `llm_service.py` | LLM interactions (OpenAI/LiteLLM) |
| `validation_service.py` | SQL syntax validation via DB |
| `vector_store.py` | Milvus CRUD operations |
| `execution_service.py` | Python code execution |
| `visualization_service.py` | Chart recommendations |
| `profiling_service.py` | Data profiling |
| `insight_service.py` | AI insight generation |

---

## Configuration

### Environment Variables

```env
# Required
OPENAI_API_KEY=sk-...
SQL_SERVER_CONNECTION_STRING=DRIVER={ODBC Driver 17 for SQL Server};SERVER=...;DATABASE=Northwind;...

# Optional
MILVUS_HOST=localhost
MILVUS_PORT=19530
OPENAI_MODEL=gpt-4o
API_KEY=your-secure-key
VECTOR_DB_ENABLED=true
```

### Runtime Configuration

Settings are loaded from `.env` file and can be modified via:
- Admin UI Settings page
- `PUT /api/v1/admin/settings` API (updates `.env` file)

**Note**: Database connections are defined in `skills/data-sources/*/` directories, not in settings.

---

## Running the Backend

### Development

```bash
# Activate virtual environment
.\myenv\Scripts\activate  # Windows
source myenv/bin/activate  # Linux/Mac

# Run with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker

```bash
docker-compose up -d
```

---

## Testing

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_generation_service_discovery.py -v
```



