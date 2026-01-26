# SQL Agent - AI Coding Instructions

## Project Architecture

This is a **Natural Language to SQL** agent with RAG-based discovery and iterative validation:

- **Backend**: FastAPI (Python) at [app/](../app) - exposes `/api/v1/discovery`, `/api/v1/generate-sql`, `/api/v1/contributions`, `/api/v1/admin/*`
- **Frontend**: React + TypeScript at [frontend/src/](../frontend/src) - chat interface with admin panel for schema/knowledge base management
- **Vector Store**: Milvus v2.3.13 with 4 collections: `schema_index` (table metadata), `fewshot_index` (knowledge base - query examples), `value_index` (lookup values), `contribution_library` (user-submitted examples pending review)
- **Database**: Microsoft SQL Server (Northwind sample database) accessed via SQLAlchemy + pyodbc

## Critical Data Flow: Query → SQL Generation

### Stage 1: Query Analysis & Intent
- **Query Classification** ([generation_service.py](../app/services/generation_service.py)): `classify_query_type()` determines if query is `database`, `general`, or `uncertain`
- **Entity Extraction**: For database queries, extract key nouns and date ranges to seed semantic metadata search
- **Complexity Scoring**: Determine if query requires multi-table joins, aggregations, or CTEs to adjust generation strategy

### Stage 2: Discovery & Context Synthesis
- **Semantic Search** ([discovery_service.py](../app/services/discovery_service.py)): 
  - Embeds user query + extracted entities with OpenAI `text-embedding-3-small` (1536 dim)
  - Vector searches Milvus for relevant tables (top 5) and similar queries (top 3)
  - Returns `DiscoveryContext` with `TableSchema[]` and knowledge base examples
- **Sample Values Injection**: Include categorical column values (e.g., Status: `['A', 'P']`) and data types to prevent type-mismatch errors
- **Knowledge Base Selection**: Inject examples specifically mapped to detected query complexity

### Stage 3: Reasoning-First Generation & Iterative Validation
- **Chain-of-Thought** ([llm_service.py](../app/services/llm_service.py)): LLM explains join logic and column selection before writing SQL
- **Mandatory Table Aliasing**: Enforce alias usage in all generated queries to prevent column ambiguity
- **Iterative Loop** (max 5 attempts):
  1. Build prompt with schema descriptions (NOT full column lists), knowledge base examples, previous SQL, and attempt history
  2. LLM generates T-SQL via `generate_sql_with_context()`
  3. **Database Validation** ([validation_service.py](../app/services/validation_service.py)): `validate_sql_with_db()` uses `SET NOEXEC ON` to parse-check syntax/permissions
  4. **Optional Execution Plan Check**: Analyze estimated query cost to warn against heavy queries
  5. **Intelligent Recovery**: If validation fails, `error_parser()` categorizes failure:
     - **Missing Object**: Extract object → re-run discovery with `{query} + {missing_object}` → update context → retry
     - **Ambiguity/Logic Error**: Feed specific T-SQL error + "Self-Correction" instruction back to LLM
     - **Type Mismatch**: Provide column definitions (VARCHAR vs INT) to LLM for correction

### Stage 4: Final Output
- Returns optimized, validated T-SQL with explanation of logic used, or structured error report after 5 attempts
- Returns `(is_valid, error_message, missing_objects[])` tuple with detailed failure categorization

## Key Patterns & Conventions

### Schema Embedding Strategy
- Tables are indexed using **natural language descriptions** only (see [ingest_service.py](../app/services/ingest_service.py))
- `TableSchema.description` should be human-readable and searchable (e.g., "Customers table containing client contact and address information")
- Columns stored as JSON in Milvus `columns_json` field but excluded from embeddings for better semantic search

### Prompt Engineering
- System prompts in `generation_service.py` use a structured format:
  ```
  Northwind Database Header
  ### KNOWLEDGE BASE EXAMPLES (previous SQL + similar queries)
  ### DATABASE SCHEMA (descriptions only, NOT columns)
  ### ATTEMPT HISTORY (previous validation errors)
  CRITICAL RULES: Only use provided tables/columns
  ```
- LLM context logs written to `F:\sql-agent2\llm_context.log` (hardcoded path for debugging)

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
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o  # Default model for SQL generation
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

- **Adding new discovery features**: Update `discovery_service.py` → modify `DiscoveryContext` schema in [schemas.py](../app/models/schemas.py) → update LLM prompt in `generation_service.py`
- **Changing validation logic**: Edit `validation_service.py` but ensure regex patterns in `generation_service.py::parse_validation_error()` match new error formats
- **New vector collections**: Add schema in `ingest_service.py`, create collection methods in `vector_store.py`, update config in [config.py](../app/core/config.py)

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
