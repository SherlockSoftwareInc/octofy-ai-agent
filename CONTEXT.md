# Octofy AI Agent - Project Overview

> A Natural Language to SQL agent with RAG-based discovery and iterative validation.

---

## What is Octofy AI Agent?

**Octofy AI Agent** is the backend API service for [Octofy Pro](https://sherlocksoftwareinc.com/). It provides a copilot experience for building SQL queries from natural language requests using advanced **Retrieval Augmented Generation (RAG)**, semantic search, and iterative validation to generate accurate, validated T-SQL for Microsoft SQL Server.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                        │
│  - Chat Interface    - Admin Panel    - Schema/KB Management   │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP/SSE
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                          │
│  /api/v1/discovery   /api/v1/generate-sql   /api/v1/execute-sql│
│  /api/v1/execute-python   /api/v1/admin/*                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   Milvus v2.3   │  │  SQL Server     │  │   OpenAI/LLM    │
│  Vector Store   │  │  (Northwind)    │  │   API           │
│  - schema_index │  │                 │  │                 │
│  - fewshot_index│  │                 │  │                 │
│  - value_index  │  │                 │  │                 │
│  - contributions│  │                 │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Natural Language to SQL** | Converts user questions into optimized, validated T-SQL queries |
| **SQL Execution & Analysis** | ⭐ NEW: Executes SQL with auto-retry, data profiling, and AI-powered insights |
| **Multi-Language Code Gen** | Supports SQL, R, SAS, and Python code generation |
| **Value Index** | Maps user terms (e.g., "North America") to exact database values |
| **Schema Management** | Admin UI for managing table schemas with Excel bulk upload |
| **Knowledge Base** | Few-shot query examples to improve LLM accuracy |
| **Semantic Search** | Milvus vector database for finding relevant tables and queries |
| **Iterative Validation** | SQL is parse-checked and auto-corrected using database feedback |
| **Contribution Library** | User-submitted examples pending admin review |
| **Secure API** | API key authentication for all endpoints |

---

## Data Flow: Query → SQL Generation

### Stage 1: Query Analysis & Intent
- **Classification**: Determines if query is `database`, `general`, or `uncertain`
- **Entity Extraction**: Extracts key nouns and date ranges
- **Complexity Scoring**: Determines if query requires joins, aggregations, or CTEs

### Stage 2: Discovery & Context Synthesis
- **Semantic Search**: Embeds query with OpenAI `text-embedding-3-small` (1536 dim)
- **Vector Search**: Searches Milvus for relevant tables (top 5) and similar queries (top 3)
- **Value Lookup**: Includes categorical column values and data types
- **Path Finding**: LLM suggests intermediate tables for multi-table joins

### Stage 3: SQL Generation & Validation
- **Chain-of-Thought**: LLM explains join logic before writing SQL
- **Iterative Loop** (max 5 attempts):
  1. Build prompt with schema descriptions and knowledge base examples
  2. LLM generates T-SQL via `generate_sql_with_context()`
  3. Database validation using `SET NOEXEC ON`
  4. Intelligent recovery on failure (re-discovery, self-correction)

### Stage 4: SQL Execution & Analysis ⭐ NEW
- **Actual Execution**: Runs validated SQL against database
- **Auto-Retry Loop** (max 5 attempts):
  1. Execute SQL with configurable timeout and row limit
  2. On error: regenerate SQL with error feedback using LLM
  3. Re-execute until success or max attempts
- **Data Profiling**: Statistical analysis of result sets (row counts, distributions, correlations)
- **AI Insights**: Automatically detects trends, outliers, correlations, and generates recommendations
- **Chart Recommendations**: Suggests optimal visualization type (bar, line, pie, etc.) based on data structure
- **Full Transparency**: Response includes auto-fix metadata when retry occurs

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React + TypeScript, Vite, TailwindCSS |
| **Backend** | FastAPI (Python), SQLAlchemy, pyodbc |
| **Vector Store** | Milvus v2.3.13 |
| **Database** | Microsoft SQL Server |
| **LLM** | OpenAI GPT-4o (configurable) |
| **Embeddings** | OpenAI text-embedding-3-small |

---

## Milvus Collections

| Collection | Purpose |
|------------|---------|
| `schema_index` | Table metadata with Markdown descriptions |
| `fewshot_index` | Knowledge base - query examples (SQL, R, SAS) |
| `value_index` | Lookup values for categorical columns |
| `contribution_library` | User-submitted examples pending review |

---

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- Docker (for Milvus)
- Microsoft SQL Server

### Installation
```bash
# Clone and install
git clone <repository-url>
cd octofy-ai-agent
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Start Milvus
docker-compose up -d

# Configure environment
cat > .env << EOF
OPENAI_API_KEY=your_openai_api_key
SQL_SERVER_CONNECTION_STRING=your_db_connection_string
EOF

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
| [GENERATE_SQL.md](GENERATE_SQL.md) | ⭐ NEW: Complete SQL generation & execution process guide |
| [SQL_EXECUTION_AUTO_RETRY_FEATURE.md](SQL_EXECUTION_AUTO_RETRY_FEATURE.md) | ⭐ NEW: SQL execution with auto-retry feature details |
| [BACKEND_API.md](BACKEND_API.md) | Complete API reference |
| [FRONTEND.md](FRONTEND.md) | Frontend architecture and components |
| [PYTHON_CODE_AUTO_RETRY_FEATURE.md](PYTHON_CODE_AUTO_RETRY_FEATURE.md) | Python execution with auto-retry |
| [VALUE_INDEX_QUICKSTART.md](VALUE_INDEX_QUICKSTART.md) | Value index setup guide |
| [EXCEL_UPLOAD_QUICKSTART.md](EXCEL_UPLOAD_QUICKSTART.md) | Bulk upload guide |
| [SCHEMA_SYNC_FEATURE.md](SCHEMA_SYNC_FEATURE.md) | Schema synchronization |

---

## Environment Variables

```env
# Required
API_KEY=change-this-to-a-secure-key
```

---

## Project Structure

```
octofy-ai-agent/
├── app/                    # Backend application
│   ├── api/endpoints/      # API route handlers
│   ├── core/               # Config, auth, database
│   ├── models/             # Pydantic schemas
│   ├── services/           # Business logic
│   │   ├── generation_service.py      # SQL generation logic
│   │   ├── validation_service.py      # SQL validation & execution ⭐ UPDATED
│   │   ├── execution_service.py       # Python code execution
│   │   ├── profiling_service.py       # Data profiling (SQL & Python)
│   │   ├── insight_service.py         # AI insights (SQL & Python)
│   │   └── visualization_service.py   # Chart recommendations
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
├── tests/                  # Test suite
└── volumes/                # Docker volumes (Milvus data)
```

