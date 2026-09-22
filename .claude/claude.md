# SQL Agent - Project Rules & Context

> **Additional Rules:** 
- See [rules/planning.md](rules/planning.md) for pre-change analysis and thought process requirements.
- See [rules/frontend-design.md](rules/frontend-design.md) for frontend design patterns and rules.

## 🛠 Tech Stack
- **Backend:** FastAPI (Python 3.x) with Pydantic models
- **Frontend:** React + TypeScript (strict mode) + Vite
- **Vector Store:** Milvus or sqlite-vec. Contract collections: `schemas` (object + column entities), `few_shots` (vector + exact-question lookup), `value_index`, data groups, precomputed queries. See `docs/VECTOR_SCHEMA.md`.
- **Database:** Microsoft SQL Server via SQLAlchemy + pyodbc
- **LLM:** OpenAI GPT-4o for T-SQL generation

## 📐 Architecture & Patterns
- **File Length:** Maximum 400 lines per file. Split large services into focused modules.
- **Services:** Single-responsibility pattern in `app/services/`. Each service handles one domain.
- **Exports:** Use named exports in TypeScript. Use module-level functions in Python.
- **Query Flow:** Wrapper gate → route → KB/precomputed fast path → KB-first discovery + RRF → attempt loop (safety → critic → SET NOEXEC ON, max 5 / 120 s). See `docs/AGENT_PROCESS.md`.

## 📝 Coding Guidelines
- **No Artifacts:** Do not generate boilerplate comments or placeholder code.
- **Full Code:** Always provide complete functions/components. Never say "X remains unchanged."
- **Type Hints:** Required for all Python function signatures. Use Pydantic for schemas.
- **T-SQL Only:** Use `SELECT TOP n` (not `LIMIT`), `DATEPART()`, table aliases required.
- **Error Recovery:** Parse SQL Server errors → re-run discovery for missing objects → retry with context.

## 🗂 File Structure Rules
- **Python Services:** `app/services/{service_name}.py` - one service per file
- **API Endpoints:** `app/api/endpoints/` - register in `app/main.py`
- **React Components:** `frontend/src/components/` - PascalCase filenames
- **React Pages:** `frontend/src/pages/` - one page per feature
- **Schemas:** `app/models/schemas.py` - all Pydantic models here

## 🧪 Testing & Verification
- **Commands:** Run `python -m pytest tests/` after logic changes
- **Key Tests:** `test_generation_service_discovery.py` validates the retry loop
- **Manual Test:** Use Swagger UI at `http://localhost:8000/docs`

## ⚙️ Environment Setup
```powershell
# Vector Store
docker-compose up -d etcd minio standalone

# Backend (port 8000)
.\myenv\Scripts\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (port 45678)
cd frontend && npm run dev
```

## ⚠️ Critical Gotchas
- **Milvus Ingestion:** Collections are dropped & recreated on ingest - not idempotent!
- **Frontend Port:** Vite runs on `45678`, not default 5173
- **Connection Strings:** Must be URL-encoded for SQLAlchemy
- **Settings File:** `.env` - loaded at runtime

## 🚫 Do NOT
- Use `LIMIT` clause (T-SQL uses `TOP`)
- Generate DDL/DML statements (SELECT only)
- Hardcode credentials in source code
- Modify vector store schema without updating `schema_contracts.py`, both providers, ingest (`schema_rows.py`), and `tests/unit/test_schema_contract.py`
- Skip validation step when modifying SQL generation logic
