# Octofy AI Agent - AI Coding Instructions

## Project Architecture

This is a **Natural Language to SQL** agent with RAG-based discovery and iterative validation:

- **Backend**: FastAPI (Python) at [app/](../app) - exposes `/api/v1/discovery`, `/api/v1/generate-sql`, `/api/v1/contributions`, `/api/v1/admin/*`
- **Frontend**: React + TypeScript at [frontend/src/](../frontend/src) - chat interface with admin panel for schema/knowledge base management
- **Vector Store**: Milvus or sqlite-vec. Contract collections include `schemas` (table/view/function **and** column entities), `few_shots` (vector + exact-question lookup), `value_index`, data groups, precomputed queries, `contribution_library`. See [docs/VECTOR_SCHEMA.md](../docs/VECTOR_SCHEMA.md).
- **Database**: Microsoft SQL Server (Northwind sample database) accessed via SQLAlchemy + pyodbc

## Critical Data Flow: Query → SQL Generation

Canonical write-up: [docs/AGENT_PROCESS.md](../docs/AGENT_PROCESS.md).

### Stage 1: Wrapper + route
- `generation_service.generate_sql_for_request()` owns `plan`/`ask` (discuss), `search`, `off_topic`, and `system_metadata`
- `queryMode=generate` calls `generate_sql_builtin()` (`app/core/orchestrator/`)
- Router sets `fresh_start` / `optimization` / `debugging` and may skip discovery or query analysis

### Stage 2: Discovery & Context Synthesis
- KB-first (`DiscoveryEngine`): exact few-shot / precomputed exits, then `kb_direct` / `kb_gap_fill` / RRF `dual_prong`
- `schemas` collection holds parent objects **and** `entity_type=Column` rows; value-index seeds use `plain_value` substring match
- Hydrator loads skills-folder markdown under a 6,400-token budget (cap 8 objects)

### Stage 3: Attempt loop (`attempts.py`)
- Max 5 attempts / 120 s. Frozen order: safety interceptor → sentinels → structural hash → critic → `SET NOEXEC ON`
- Missing objects expand discovery (cap 5); the same miss twice trips `deterministic_missing_object`
- Repeated structural hash exits as a hallucination loop
- Prompts are built in `app/core/orchestrator/prompts.py` (dialect, analysis, examples, mappings, schemas, history)

### Stage 4: Final Output
- `GenerateSQLResponse` with `sql`, `discovery_branch`, `success`, attempt/token/timing fields, optional `failure_report`

## Key Patterns & Conventions

### Schema Embedding Strategy
- `schemas` stores **parent** rows (`entity_type` = Table/View/Function) and **column** rows (`entity_type=Column`)
- Embedding text is built in `schema_rows.py` / `schema_contracts.py` (`parent_embedding_text`, `column_embedding_text`)
- Hydration uses skills-folder markdown, not the embedding payload
- Change the contract in `schema_contracts.py`, both providers, ingest, and `tests/unit/test_schema_contract.py`

### Prompt Engineering
- System prompts live in `app/core/orchestrator/prompts.py`: dialect, generation mode, query analysis, data groups, examples, value mappings, selected + supplementary schemas, attempt history

### Error Handling
- LLM can return validation error strings like `"COLUMN_VALIDATION_ERROR: Cannot find column [X]"` which triggers re-discovery
- SQL Server errors parsed via regex: `Invalid object name 'xxx'` → extract `xxx` for targeted re-discovery

### Uncertain Query Classification & Frontend Clarification
When `classify_query_type()` returns `"uncertain"` (ambiguous queries without clear database/general indicators):

1. **Backend Response**: Returns `GenerateSQLResponse` with `query_type="uncertain"` and explanation about Northwind database context
2. **Frontend Detection**: [App.tsx](../frontend/src/App.tsx) checks `result.query_type === 'uncertain'` and creates message with `needsClarification: true`
3. **UI Presentation**: Displays two buttons:
   - 🔍 **Search Database**: Re-runs query through discovery → SQL generation pipeline
   - 💬 **General Answer**: Bypasses discovery and sends to LLM for conversational response
4. **Resolution**: `handleClarificationChoice()` re-processes original user query with explicit intent, updating the AI message in-place

This prevents the agent from making incorrect assumptions about ambiguous queries like "find products" (could be database query or general product information).

### T-SQL Conventions
- All prompts specify **"T-SQL developer for Microsoft SQL Server"** context (see [llm_service.py](../app/services/llm_service.py))
- LLM instructed to use T-SQL-specific syntax:
  - `SELECT TOP n` instead of `LIMIT n`
  - `DATEPART()` for date component extraction
  - Qualify table names with schema: `dbo.TableName`
- Temperature set to 0 for deterministic SQL generation
- Markdown code block stripping: `sql.replace("```sql", "").replace("```", "").strip()` applied to all LLM outputs

## Development Workflows

### Local Development Setup
```powershell
# 1. Start Milvus only (not backend container)
docker-compose up -d etcd minio standalone

# 2. Activate venv and run backend locally
.\myenv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. Run frontend
cd frontend
npm run dev  # Runs on port 45678
```

**Alternative**: Use `rebuild_and_deploy.bat` (Windows batch script) to automate the above.

### First-Time Setup
After Milvus starts, backend auto-ingests schemas on startup if `schema_index` is empty (see `main.py` startup event). Manual ingestion:
```powershell
python scripts/ingest_metadata.py
```

### Testing
```powershell
python -m pytest tests/  # Key test: test_generation_service_discovery.py validates retry logic
```

## Environment Variables (.env)
```env
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o  # Default model for SQL generation
SQL_SERVER_CONNECTION_STRING=DRIVER={ODBC Driver 17 for SQL Server};SERVER=...;DATABASE=Northwind;...
MILVUS_HOST=localhost  # Use "standalone" in docker-compose for backend container
MILVUS_PORT=19530
```

## Project-Specific Gotchas

1. **Connection String Encoding**: `database.py` auto-converts ODBC connection strings to SQLAlchemy URLs: `mssql+pyodbc:///?odbc_connect={quoted_params}`

2. **Milvus Collection Initialization**: Collections are dropped and recreated on every ingestion run (see `create_milvus_collections()`) - not idempotent!

3. **Frontend Port**: Vite dev server runs on `:45678` (non-default, likely to avoid conflicts) - see [vite.config.ts](../frontend/vite.config.ts)

4. **Admin Routes**: Separate admin interface at `/admin` in frontend (React state router) for managing schemas and knowledge base - accessible via UI navigation

5. **Vector Store Singleton**: `get_vector_store()` returns `MilvusVectorStore` instance - connection established at import time, not lazy-loaded

## When Modifying Core Logic

- **Adding new discovery features**: Update `discovery_engine.py` and pipeline models in [pipeline.py](../app/models/pipeline.py); keep RRF weights/thresholds in `constants.py` unless the product change is explicit
- **Changing validation logic**: Edit `attempts.py` / `sql_validator.py`; do not reorder the frozen validation stack
- **New vector collections**: Add the spec to `schema_contracts.py`, both providers, ingest, and `tests/unit/test_schema_contract.py`

## API Endpoints Quick Reference
- `POST /api/v1/discovery` - Get relevant schemas for query
- `POST /api/v1/generate-sql` - Full generation with optional context override
- `POST /api/v1/contributions` - Submit a contribution (user-facing)
- `GET /api/v1/admin/contributions` - List pending contributions (admin)
- `POST /api/v1/admin/contributions/approve` - Approve contribution to Knowledge Base
- `DELETE /api/v1/admin/contributions/{id}` - Reject/delete contribution
- `POST /api/v1/admin/ingest-metadata` - Re-index all schemas from SQL Server
- `GET /api/v1/admin/schemas` - List indexed schemas
- `POST /api/v1/admin/fewshots` - Add new knowledge base example

Full API docs: http://localhost:8000/docs (Swagger UI)
