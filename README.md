# Octofy AI Agent

**Octofy AI Agent** is the backend API service for [Octofy Pro](https://sherlocksoftwareinc.com/). It turns natural-language questions into validated T-SQL (and Python, R, or SAS) using retrieval-augmented generation, semantic search, and an iterative attempt loop.

The service is designed as a copilot: users ask questions in chat, the agent discovers relevant schema and examples, generates dialect-correct SQL, parse-checks it against the warehouse, and optionally executes the statement with profiling and insights.

---

## Overview

A typical request flows through a FastAPI wrapper, then into a built-in orchestrator:

1. **Mode gate** — `plan` / `ask` stay conversational; `search` returns objects; `generate` produces code.
2. **Conversational context** — vague follow-ups are rewritten against recent turns, and active filters carry forward across a chat session.
3. **Route** — the request is classified as a fresh start, optimization, refinement, drill-down, or debugging turn.
4. **Discovery** — knowledge-base first, then reciprocal-rank fusion of schema vectors, value-index hits, data groups, and optional BM25.
5. **Attempt loop** — up to 5 attempts / 120 seconds: safety checks, critic, and database parse validation (`SET NOEXEC ON` on SQL Server).
6. **Optional execute** — a separate endpoint runs the SQL, retries on runtime errors, and can attach a data profile, insights, and a chart recommendation.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Auth)                      │
│  Chat  ·  Admin panel  ·  Conversations  ·  User profile        │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP / SSE  (X-API-Key)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI :8000)                    │
│  /api/v1/generate-sql  ·  /execute-sql  ·  /discovery           │
│  /api/v1/auth/*  ·  /users/*  ·  /conversations/*  ·  /admin/*  │
└───────┬──────────────────────┬──────────────────────┬───────────┘
        ▼                      ▼                      ▼
 PostgreSQL 15          Vector store              SQL Server
 users & convos         Milvus or sqlite-vec      warehouse
                        partitioned by            (or Excel files)
                        data_source_id
                               │
                               ▼
                         LLM + embeddings
                    (OpenAI-compatible / LiteLLM)
```

---

## Main features

| Feature | What it does |
|---------|----------------|
| **Natural language → SQL** | Converts questions into validated T-SQL for Microsoft SQL Server. |
| **Multi-language codegen** | Same pipeline for Python, R, and SAS (`target_language`). |
| **Query modes** | `generate`, `search`, `plan`, `ask`, and `code_advisor`. Planning/ask modes explore intent without emitting SQL. |
| **Conversational refinement** | Coreference rewrite of short follow-ups (`I need all order details` → `… for chocolate Products`) plus session filter inheritance, replacement, and clear. |
| **KB-first discovery** | Exact few-shot / precomputed hits short-circuit generation; otherwise RRF ranks schema, values, and data groups. |
| **Value index** | Maps everyday terms (for example “North America”) to exact `schema.table.column` values so generated SQL uses real literals. |
| **Iterative validation** | Safety interceptor, structural hash, LLM critic, and database parse-check; missing objects expand discovery. |
| **Execute + analyze** | Run SQL or Python with auto-retry, optional profiling, insights, and chart hints. |
| **Multi-source** | Each warehouse is a `source_id`. Vector collections and catalog lookups are partitioned by that id. |
| **Admin governance** | Schema index, knowledge base (few-shots), value index, data sources, contributions, and users. |
| **Skills / markdown catalog** | Schema objects and business groups stored as markdown and hydrated into the generation prompt under a token budget. |
| **Auth** | Per-user API keys (`X-API-Key`) with admin/user roles. Login is public; most other routes require a key. |
| **Streaming** | Generation endpoints stream Server-Sent Events (`status`, `result`, `done`, `error`). |

---

## Technology stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, Pydantic v2, SQLAlchemy, pyodbc, LiteLLM |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| User store | PostgreSQL 15 |
| Vector store | Milvus 2.3 (default) or sqlite-vec; same contract (`VECTOR_SCHEMA_VERSION` 1.1.0) |
| Warehouse | Microsoft SQL Server (ODBC Driver 17) |
| LLM | Any OpenAI-compatible API (OpenAI, Azure, Ollama, …) via LiteLLM |
| Embeddings | `text-embedding-3-small` (1536-d cosine) by default |

---

## Prerequisites

- **Python 3.11+** (the backend Docker image is `python:3.11-slim`)
- **Node.js 20+** (frontend Docker image is `node:20`)
- **Docker** for Milvus, etcd, MinIO, and PostgreSQL
- **Microsoft SQL Server** plus **ODBC Driver 17 for SQL Server**
- An **OpenAI-compatible LLM API key** (and embedding access if separate)

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/SherlockSoftwareInc/octofy-ai-agent.git
cd octofy-ai-agent

pip install -r requirements.txt
pip install -r requirements-dev.txt   # tests

cd frontend
npm install
cd ..
```

### 2. Start infrastructure

```bash
docker-compose up -d
```

This starts:

| Service | Host port | Role |
|---------|-----------|------|
| PostgreSQL 15 | `5432` | Users and conversation history |
| Milvus standalone | `19630` | Vector search (`19530` inside the network) |
| etcd | internal | Milvus metadata |
| MinIO | `9100` / `9101` | Milvus object storage |

### 3. Configure environment

Copy `.env.example` to `.env` and fill in secrets:

```bash
cp .env.example .env
```

Minimum required values:

```env
# Auth
API_KEY=change-this-to-a-secure-key
JWT_SECRET_KEY=***REMOVED***

# PostgreSQL (matches docker-compose defaults)
POSTGRES_USER=octofy
POSTGRES_PASSWORD=***REMOVED***
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=octofy_users

# LLM
LLM_API_KEY=your_llm_api_key
LLM_MODEL=gpt-4o
# LLM_ENDPOINT=https://api.openai.com/v1   # optional; any OpenAI-compatible base URL

# Warehouse
SQL_SERVER_CONNECTION_STRING=DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=Northwind;Trusted_Connection=yes

# Vector store
VECTOR_DB_ENABLED=true
VECTOR_PROVIDER=milvus
MILVUS_HOST=localhost
MILVUS_PORT=19630
```

SQL authentication example:

```env
SQL_SERVER_CONNECTION_STRING=DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=Northwind;UID=sa;PWD=your_password
```

### 4. Initialize users and schema

User tables are created on backend startup. You can also seed them explicitly:

```bash
python scripts/init_user_db.py
```

If no users exist, a default admin is created:

| Field | Value |
|-------|--------|
| Username | `admin` |
| Password | `admin123` |

Change this password immediately after first login.

Ingest warehouse metadata into the vector index:

```bash
python scripts/ingest_metadata.py
```

Alternatively, register a data source in **Admin → Data Sources** and sync the schema from the UI.

### 5. Run the apps

Backend (port **8000**):

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (port **45678**, proxies `/api` to the backend):

```bash
cd frontend
npm run dev
```

| Surface | URL |
|---------|-----|
| Chat UI | http://localhost:45678 |
| Admin | http://localhost:45678/admin |
| Health | http://localhost:8000/ → `{"message": "Database AI Agent API is running"}` |
| Swagger | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| OpenAPI | http://localhost:8000/api/v1/openapi.json |

---

## Usage examples

All authenticated requests send the user’s API key:

```http
X-API-Key: <access_token from login>
```

Login returns that key as `access_token` (`token_type` is `api-key`).

### Login

```bash
curl -s http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

```json
{
  "access_token": "oct_...",
  "token_type": "api-key",
  "user": { "username": "admin", "role": "admin" }
}
```

### Generate SQL (SSE)

`source_id` is required. Resolve it from Admin → Data Sources, or:

```bash
curl -s "http://localhost:8000/api/v1/admin/data-sources" \
  -H "X-API-Key: $API_KEY"
```

```bash
curl -N http://localhost:8000/api/v1/generate-sql \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "query": "Show the top 10 customers by order count",
    "queryMode": "generate",
    "source_id": "northwind"
  }'
```

Typical stream:

```
data: {"type":"status","step":"discovery","message":"Discovering relevant objects"}

data: {"type":"result","payload":{"sql":"SELECT TOP 10 ...","success":true,"discovery_branch":"dual_prong"}}

data: {"type":"done"}
```

### Follow-up with session filters

Pass `session_id` (the chat/conversation id) so filters inherit, replace, or clear across turns. Also send the previous SQL as `existing_code` / `previousSQL` when the user is refining the editor query.

```bash
curl -N http://localhost:8000/api/v1/generate-sql \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "query": "I need all order details",
    "queryMode": "generate",
    "source_id": "northwind",
    "session_id": "conv-123",
    "existing_code": "SELECT ProductName FROM dbo.Products WHERE ProductName LIKE '\''%chocolate%'\''",
    "queryHistory": "Q: Show chocolate products\nA: SELECT ProductName FROM dbo.Products WHERE ProductName LIKE '\''%chocolate%'\''"
  }'
```

The orchestrator rewrites the follow-up against active filters (for example, keep the chocolate product constraint) and treats the turn as **refinement** rather than a full rewrite. Phrases like `start over`, `new query`, or `clear filters` reset that state.

### Plan / ask (no SQL)

```bash
curl -N http://localhost:8000/api/v1/generate-sql \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "query": "What tables would I use to analyze freight costs by ship country?",
    "queryMode": "ask",
    "source_id": "northwind"
  }'
```

### Execute SQL

Generation parse-checks only. Execution is a second call:

```bash
curl -s http://localhost:8000/api/v1/execute-sql \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "sql": "SELECT TOP 10 CustomerID, COUNT(*) AS OrderCount FROM dbo.Orders GROUP BY CustomerID ORDER BY OrderCount DESC",
    "source_id": "northwind",
    "timeout_seconds": 30,
    "max_rows": 10000
  }'
```

When `ENABLE_AI_DATA_ANALYSIS=true`, the response can include `data_profile`, `insights`, and a `recommendation` chart. Runtime errors trigger up to five regenerate-and-retry attempts.

### Other languages

```bash
# Python
curl -N http://localhost:8000/api/v1/generate-python \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"query":"Load orders into a pandas DataFrame and plot monthly counts","source_id":"northwind"}'

# R
curl -N http://localhost:8000/api/v1/generate-r ...

# SAS
curl -N http://localhost:8000/api/v1/generate-sas ...
```

### Chat UI

1. Open http://localhost:45678 and sign in.
2. Pick a data source in the sidebar.
3. Choose a mode: Ask, Generate SQL, Python, R, SAS, or Code Advisor.
4. Ask a question. Status steps stream into the thread; SQL/code appears with an explanation.
5. Run the statement to see a result grid, optional insights, and a chart suggestion.
6. Continue in the same conversation to refine filters, add columns, or drill down.

---

## Admin workflows

Open **Admin** from the chat UI (`/admin`). Pages:

| Page | Purpose |
|------|---------|
| **Data Sources** | Register warehouses, test connections, scan objects, set primary source. |
| **Schema Index** | Sync tables/views/functions from the database, Excel bulk import, descriptions. |
| **Knowledge Base** | Few-shot question/SQL pairs that enable exact-match fast paths. |
| **Contributions** | User-submitted examples pending admin approval. |
| **Value Index** | Categorical value map used at generation time. |
| **User Management** | Create users, roles, regenerate API keys. |
| **Settings** | LLM, embeddings, and connectivity checks. |

### Value index (Excel)

1. Admin → **Value Index** → download the template.
2. Fill `value`, `schema_name`, `table_name`, `column_name`.
3. Upload in append or replace mode.

That mapping is what lets “North America” become the literal stored in `dbo.Region.RegionDescription` instead of a guessed string. Details: [docs/VALUE_INDEX_QUICKSTART.md](docs/VALUE_INDEX_QUICKSTART.md).

### Schema sync

Use **Sync** / **Sync Full** in Schema Index, or:

```bash
python scripts/ingest_metadata.py
```

---

## API surface

Base path: `/api/v1`. Full reference: [docs/BACKEND_API.md](docs/BACKEND_API.md).

| Area | Examples |
|------|----------|
| Discovery | `POST /discovery` |
| Generation (SSE) | `POST /generate-sql`, `/generate-python`, `/generate-r`, `/generate-sas`, `/code-advisor` |
| Execution | `POST /execute-sql`, `/execute-python` |
| Summaries | `POST /planning-summary`, `/summarize-results` |
| Auth / users | `POST /auth/login`, `GET /auth/me`, admin `/admin/users` |
| Conversations | `GET/POST /conversations` |
| Admin | schema, few-shots, values, data sources, schema tree, skills, contributions |

`GenerateSQLRequest` fields that change the path:

| Field | Effect |
|-------|--------|
| `queryMode` | `generate` enters the orchestrator; `plan` / `ask` / `search` do not |
| `source_id` | Selects the per-source store bundle (required on generate HTTP) |
| `database_objects` | Pins; catalog-validated; fail-fast if missing |
| `existing_code` / `previousSQL` | Optimization, refinement, or debug |
| `error_message` | Debugging route (fix the provided code) |
| `session_id` | Cross-turn filter state |
| `semantic_mode` | Semantic-model compile path (SQL only) |
| `forceGeneral` | Skip SQL and chat instead |

---

## Project structure

```
octofy-ai-agent/
├── app/
│   ├── api/endpoints/          # FastAPI routers
│   ├── core/
│   │   ├── orchestrator/       # Route → discover → attempt loop
│   │   ├── auth.py
│   │   ├── config.py
│   │   └── constants.py        # Built-in thresholds (do not retune)
│   ├── models/                 # Pydantic + SQLAlchemy
│   ├── services/               # Generation wrapper, execute, stores
│   │   └── stores/             # Milvus / sqlite-vec contract
│   └── utils/
├── frontend/                   # Vite + React chat and admin UI
├── scripts/                    # Ingest, user DB init, migrations
├── tests/                      # unit / contract / parity
├── docs/                       # Design and API docs
├── docker-compose.yml          # etcd, MinIO, Milvus, PostgreSQL
└── .env.example
```

Orchestrator modules:

| File | Role |
|------|------|
| `app/services/generation_service.py` | Mode gate, discuss, catalog SQL |
| `app/core/orchestrator/builtin_sql_generator.py` | Generate path |
| `preprocessing.py`, `coreference.py`, `session_context.py` | History fold, rewrite, filters |
| `scenario.py`, `router.py` | Fresh start / optimize / refine / drill-down / debug |
| `discovery_engine.py` | KB-first + RRF |
| `attempts.py`, `prompts.py` | Attempt loop and dialect prompts |

---

## Configuration notes

| Variable | Default | Notes |
|----------|---------|--------|
| `BUILTIN_SQL_GENERATOR` | `true` | Built-in orchestrator (recommended) |
| `VECTOR_PROVIDER` | `milvus` | Falls back to sqlite-vec if Milvus is unreachable |
| `ENABLE_AI_DATA_ANALYSIS` | `true` | Profiling, insights, chart after execute |
| `ENABLE_BM25_RETRIEVAL` | `false` | Optional lexical rerank |
| `ENABLE_SEMANTIC_LAYER_PER_DATA_SOURCE` | `{}` | JSON map of `source_id` → enabled |
| `OBJECT_SEARCH_VECTOR_SCORE_THRESHOLD` | `0.5` | Clamped to `[0, 1]` |

Retry budgets live in `app/core/constants.py` (`MaxRetries = 5`, `MaxGenerationTimeMs = 120000`) and should stay aligned with the desktop engine.

Vector collections (all partitioned by `data_source_id`): `schemas`, `few_shots`, `value_index`, `data_group_*`, `vec_data_group_queries`, `semantic_*`, `contribution_library`. See [docs/VECTOR_SCHEMA.md](docs/VECTOR_SCHEMA.md).

---

## Testing

```bash
pip install -r requirements-dev.txt
python -m pytest
python -m pytest tests/unit -v
```

Frontend:

```bash
cd frontend
npm test
```

Tests mock OpenAI and Milvus. Layout: `tests/unit`, `tests/contract`, `tests/parity`, plus module-level files. More detail: [tests/README.md](tests/README.md).

---

## Docker

Infrastructure only (typical local workflow):

```bash
docker-compose up -d
```

Backend and frontend also have their own images (`app/Dockerfile`, `frontend/Dockerfile`). The backend image installs ODBC Driver 17 and serves uvicorn on port 8000. The frontend image is a multi-stage Vite build served by nginx.

Volume root defaults to `./volumes` (etcd, MinIO, Milvus, PostgreSQL). Override with `DOCKER_VOLUME_DIRECTORY`.

---

## Security

- Send `X-API-Key` on every authenticated route.
- Login (`POST /api/v1/auth/login`) is public.
- Admin routes require an active admin key.
- Change `API_KEY`, `JWT_SECRET_KEY`, the default admin password, and warehouse credentials before any shared deployment.
- Generation blocks write statements unless the user explicitly asked for them.

---

## Documentation

Start with the generate pipeline:

1. [docs/AGENT_PROCESS.md](docs/AGENT_PROCESS.md) — stages, branches, attempt loop
2. [docs/VECTOR_SCHEMA.md](docs/VECTOR_SCHEMA.md) — collections and `source_id` partitioning
3. [docs/REQUEST_TO_CODE_FLOW.md](docs/REQUEST_TO_CODE_FLOW.md) — HTTP/SSE path
4. [docs/DISCOVERY_STRATEGY_IMPLEMENTATION.md](docs/DISCOVERY_STRATEGY_IMPLEMENTATION.md) — KB-first + RRF
5. [docs/BACKEND_API.md](docs/BACKEND_API.md) — endpoint reference

Also useful:

| Doc | Topic |
|-----|--------|
| [docs/CHATBOT.md](docs/CHATBOT.md) | Chat UI capabilities |
| [docs/GENERATE_SQL.md](docs/GENERATE_SQL.md) | Generate vs execute |
| [docs/PLANNING_MODE_FLOW.md](docs/PLANNING_MODE_FLOW.md) | Plan / ask modes |
| [docs/plans/2026-09-20-conversational-context-and-refinement.md](docs/plans/2026-09-20-conversational-context-and-refinement.md) | Scenarios, coreference, session filters |
| [docs/VALUE_INDEX_QUICKSTART.md](docs/VALUE_INDEX_QUICKSTART.md) | Value index setup |
| [docs/INDEX.md](docs/INDEX.md) | Full doc index |
| [CONTEXT.md](CONTEXT.md) | Project overview for contributors |
