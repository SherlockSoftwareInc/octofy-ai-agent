# Octofy AI Agent - Project Overview

> A Natural Language to SQL agent with RAG-based discovery and iterative validation.

---

## What is Octofy AI Agent?

**Octofy AI Agent** is the backend API service for [Octofy Pro](https://sherlocksoftwareinc.com/). It provides a copilot experience for building SQL queries from natural language requests using advanced **Retrieval Augmented Generation (RAG)**, semantic search, and iterative validation to generate accurate, validated T-SQL for Microsoft SQL Server.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Auth)                      │
│  - Login/Auth    - Chat Interface    - Admin Panel             │
│  - User Profile  - Conversation History                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP/SSE (JWT or API Key)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                          │
│  /api/v1/auth/*   /api/v1/users/*   /api/v1/conversations/*   │
│  /api/v1/discovery   /api/v1/generate-sql   /api/v1/admin/*   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
      ┌────────────────────────┼────────────────────┐
      ▼                        ▼                    ▼
┌──────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ PostgreSQL   │  │ Vector store    │  │  SQL Server     │
│ (Users &     │  │ Milvus or       │  │  (Data Source)  │
│ Convos)      │  │ sqlite-vec      │  │                 │
│              │  │ partitioned by  │  │                 │
│              │  │ data_source_id  │  │                 │
└──────────────┘  └─────────────────┘  └─────────────────┘
                         │
                         ▼
                  ┌─────────────────┐
                  │   LLM    │
                  │   API           │
                  └─────────────────┘
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **User Management** | ⭐ NEW: Multi-user authentication with JWT tokens and role-based access control |
| **Conversation History** | ⭐ NEW: Persistent chat history synced across devices via PostgreSQL |
| **Natural Language to SQL** | Converts user questions into optimized, validated T-SQL queries |
| **SQL Execution & Analysis** | Executes SQL with auto-retry, data profiling, and AI-powered insights |
| **Multi-Language Code Gen** | Supports SQL, R, SAS, and Python code generation |
| **Value Index** | Maps user terms (e.g., "North America") to exact database values |
| **Schema Management** | Admin UI for managing table schemas with Excel bulk upload |
| **Knowledge Base** | Few-shot query examples to improve LLM accuracy |
| **Semantic Search** | Milvus vector database for finding relevant tables and queries |
| **Iterative Validation** | SQL is parse-checked and auto-corrected using database feedback |
| **Contribution Library** | User-submitted examples pending admin review |
| **Secure API** | JWT token and API key authentication with admin/user roles |

---

## Data Flow: Query → SQL Generation

The generate path is the built-in orchestrator (`app/core/orchestrator/`). Full write-up: [docs/AGENT_PROCESS.md](docs/AGENT_PROCESS.md).

### Stage 1: Wrapper gate
- `plan` / `ask` → discuss service (no SQL)
- `search` → object list
- Intent `off_topic` / `forceGeneral` → conversational reply
- Intent `system_metadata` → catalog-view SQL
- `generate` → hand off to `generate_sql_builtin()` for a resolved `source_id`

### Stage 2: Route, fast path, discovery
- Conversational context: coreference rewrite of vague follow-ups + session filter inheritance (`session_id`), before classification
- Deterministic route scenarios (`fresh_start` / `optimization` / `refinement` / `drill_down` / `debugging`) plus LLM intent (`db_query` / `optimize_code` / `refine_query` / `app_feature` / `off_topic`)
- Exact exits: few-shot key, precomputed question, or KB vector distance ≤ 0.05 (bypassed on refinement turns that carry active filters)
- Otherwise KB-first discovery, then RRF of schema vectors (table **and** column entities), value-index seeds, data groups, optional BM25
- Refinement/drill-down keeps discovery enabled, anchors the editor SQL's tables as required, and preserves active filters
- Hydrate skills-folder markdown under a token budget (12-object cap on refinement turns)

### Stage 3: Attempt loop (max 5, 120 s)
1. Build dialect prompt (or SMQ payload in semantic mode)
2. Frozen validation: safety → sentinels → structural hash → critic → `SET NOEXEC ON`
3. Missing-object expansion and hallucination breaker

### Stage 4: SQL Execution & Analysis
- Separate `POST /api/v1/execute-sql` (not the generate loop)
- Auto-retry on runtime errors (max 5)
- Optional profiling, insights, and chart recommendation when `ENABLE_AI_DATA_ANALYSIS` is true

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React + TypeScript, Vite, TailwindCSS |
| **Backend** | FastAPI (Python), SQLAlchemy, pyodbc |
| **User Database** | PostgreSQL 15+ |
| **Vector Store** | Milvus (default) or sqlite-vec; same contract |
| **Data Warehouse** | Microsoft SQL Server |
| **LLM** | OpenAI GPT-4o (configurable) |
| **Embeddings** | OpenAI text-embedding-3-small (1536-d) |
| **Authentication** | JWT (python-jose), Bcrypt (passlib) |

---

## Vector Collections

Contract version `1.1.0`. Every row is partitioned by `data_source_id`. Full field list: [docs/VECTOR_SCHEMA.md](docs/VECTOR_SCHEMA.md).

| Collection | Purpose |
|------------|---------|
| `schemas` | Table / view / function **and** column entities (1536-d cosine) |
| `few_shots` | Knowledge-base examples (vector + exact-question lookup) |
| `value_index` | Categorical values; query-time substring on `plain_value` |
| `data_group_*` | Business groups, members, and cached embeddings |
| `vec_data_group_queries` | Precomputed approved questions (optional SMQ) |
| `semantic_*` | Semantic models, measures, dimensions, joins |
| `contribution_library` | User-submitted examples pending review |
| `embedding_cache` | Shared embedding cache |

---

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- Docker (for Milvus + PostgreSQL)
- Microsoft SQL Server

### Installation
```bash
# Clone and install
git clone <repository-url>
cd octofy-ai-agent
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Start infrastructure (Milvus + PostgreSQL)
docker-compose up -d

# Configure environment
cat > .env << EOF
LLM_API_KEY=your_llm_api_key
SQL_SERVER_CONNECTION_STRING=your_db_connection_string
JWT_SECRET_KEY=your-super-secret-jwt-key
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
EOF

# Initialize user database and create default admin
python scripts/init_user_db.py

# Ingest schemas
python scripts/ingest_metadata.py
```

### Running
```bash
# Backend (port 8000)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (port 45678)
cd frontend && npm run dev
```

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [docs/SQL_GENERATION_BACKEND_BLUEPRINT.md](docs/SQL_GENERATION_BACKEND_BLUEPRINT.md) | End-to-end build specification of the backend SQL-generation process (for re-implementing the agent, e.g. via vibe coding) |
| [docs/AGENT_PROCESS.md](docs/AGENT_PROCESS.md) | Canonical generate pipeline |
| [docs/plans/2026-09-20-conversational-context-and-refinement.md](docs/plans/2026-09-20-conversational-context-and-refinement.md) | Scenario routing, coreference, session filters, prompt split |
| [docs/VECTOR_SCHEMA.md](docs/VECTOR_SCHEMA.md) | Vector collection contract |
| [docs/GENERATE_SQL.md](docs/GENERATE_SQL.md) | Generate + execute process |
| [docs/REQUEST_TO_CODE_FLOW.md](docs/REQUEST_TO_CODE_FLOW.md) | HTTP/SSE path into the orchestrator |
| [USER_MANAGEMENT.md](USER_MANAGEMENT.md) | User management and authentication |
| [SQL_EXECUTION_AUTO_RETRY_FEATURE.md](SQL_EXECUTION_AUTO_RETRY_FEATURE.md) | SQL execution with auto-retry feature details |
| [BACKEND_API.md](BACKEND_API.md) | Complete API reference |
| [FRONTEND.md](FRONTEND.md) | Frontend architecture and components |
| [PYTHON_CODE_AUTO_RETRY_FEATURE.md](PYTHON_CODE_AUTO_RETRY_FEATURE.md) | Python execution with auto-retry |
| [VALUE_INDEX_QUICKSTART.md](VALUE_INDEX_QUICKSTART.md) | Value index setup guide |
| [EXCEL_UPLOAD_QUICKSTART.md](EXCEL_UPLOAD_QUICKSTART.md) | Bulk upload guide |
| [SCHEMA_SYNC_FEATURE.md](SCHEMA_SYNC_FEATURE.md) | Schema synchronization |

---

## Environment Variables

```env
# Required - Authentication
API_KEY=change-this-to-a-secure-key
JWT_SECRET_KEY=your-super-secret-jwt-key-min-32-chars
JWT_ACCESS_TOKEN_EXPIRE_DAYS=7

# Required - PostgreSQL
POSTGRES_USER=octofy
POSTGRES_PASSWORD=***REMOVED***
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=octofy_users

# Required - LLM
LLM_API_KEY=your_llm_api_key

# Optional - Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19630
```

---

## Project Structure

```
octofy-ai-agent/
├── app/                    # Backend application
│   ├── api/endpoints/      # API route handlers
│   │   ├── users.py               # ⭐ NEW: User management endpoints
│   │   ├── conversations.py       # ⭐ NEW: Conversation history endpoints
│   │   ├── generation.py          # SQL generation endpoints
│   │   └── admin.py              # Admin panel endpoints
│   ├── core/               # Config, auth, orchestrator
│   │   ├── auth.py
│   │   ├── user_database.py
│   │   ├── config.py
│   │   ├── constants.py           # Built-in thresholds (do not retune)
│   │   └── orchestrator/          # generate_sql_builtin pipeline
│   ├── models/             # Pydantic schemas
│   │   ├── pipeline.py            # AgentRequest, DiscoveryResult, ...
│   │   ├── user_models.py
│   │   ├── user_schemas.py
│   │   └── schemas.py
│   ├── services/           # Business logic
│   │   ├── generation_service.py  # Wrapper + non-generate modes
│   │   ├── stores/                # Vector contract + providers
│   │   ├── validation_service.py
│   │   └── execution_service.py
│   └── utils/              # Utilities
├── frontend/               # React frontend
│   ├── src/
│   │   ├── api/            # API client
│   │   ├── components/     # UI components
│   │   ├── pages/          # Page components
│   │   └── types/          # TypeScript types
│   └── vite.config.ts
├── config/                 # Runtime configuration
├── scripts/                # Utility scripts
│   └── init_user_db.py           # ⭐ NEW: Initialize user database
├── tests/                  # Test suite
├── volumes/                # Docker volumes (Milvus + PostgreSQL data)
├── USER_MANAGEMENT.md      # ⭐ NEW: User management documentation
└── docker-compose.yml      # ⭐ UPDATED: Added PostgreSQL service
```

