
# Octofy AI Agent – API Copilot for SQL Generation

**Octofy AI Agent** is the backend API service for [Octofy Pro](https://sherlocksoftwareinc.com/). Its main purpose is to provide API endpoints that allow Octofy Pro to offer a copilot experience for building SQL queries from user natural language requests. The agent uses advanced Retrieval Augmented Generation (RAG), semantic search, and iterative validation to generate accurate, validated T-SQL for Microsoft SQL Server.

---

## Features

- **Natural Language to SQL**: Converts user questions into optimized, validated T-SQL queries.
- **Value Index**: Maps user terms (e.g., "North America") to exact database values and locations using a pre-indexed Excel manifest, preventing invalid SQL.
- **Schema & Knowledge Base Management**: Admin UI for managing table schemas and few-shot query examples, with Excel bulk upload support.
- **Semantic Search**: Uses Milvus vector database to find relevant tables, values, and similar queries.
- **Iterative Validation**: SQL is parse-checked and auto-corrected using database feedback and LLM reasoning.
- **Secure API**: API key authentication for all endpoints.
- **Dockerized**: Backend, frontend, and Milvus can be run with Docker Compose.

---

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- Docker (for Milvus vector DB)
- Microsoft SQL Server (Northwind sample recommended)

### Installation
1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd octofy-ai-agent
   ```
2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # For development/testing
   ```
3. **Install Node.js dependencies**
   ```bash
   cd frontend
   npm install
   cd ..
   ```
4. **Start Milvus and dependencies**
   ```bash
   docker-compose up -d
   ```
5. **Ingest database schemas**
   ```bash
   python scripts/ingest_metadata.py
   ```
6. **Configure environment**
   Create a `.env` file:
   ```env
   LLM_API_KEY=your_llm_api_key
   SQL_SERVER_CONNECTION_STRING=your_db_connection_string
   ```

### Running the Application
**Backend:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
**Frontend:**
```bash
cd frontend
npm run dev
```
The frontend runs on [http://localhost:45678](http://localhost:45678).

---

## Value Index: How to Use
1. Go to **Admin → Value Index**.
2. Download the Excel template.
3. Fill in your values (value, schema_name, table_name, column_name).
4. Upload the file (append or replace mode).
5. Your values are now used to improve SQL generation.

See `VALUE_INDEX_QUICKSTART.md` for a step-by-step guide.

---

## Admin Features
- **Schema Management**: Bulk import/update table schemas via Excel.
- **Few-Shot Examples**: Upload Q&A pairs to improve LLM accuracy.
- **Value Index**: Manage mappings for categorical values.
- **Progress Tracking**: Real-time upload progress and navigation prevention.
- **Sync All Schemas**: One-click rebuild of schema index from the database.

---

## Testing
Install test dependencies:
```bash
pip install -r requirements-dev.txt
```
Run all tests:
```bash
python -m pytest
```
See `tests/README.md` for details.

---

## Dockerization
You can run backend, frontend, and Milvus with Docker Compose:
```bash
docker-compose up -d
```
See `Dockerize backend and frontend plan.md` for more.

---

## Security
- All API endpoints require an API key.
- See `TEST_RESULTS.md` for authentication test results.

---

## Documentation
- **Value Index**: `VALUE_INDEX_FEATURE.md`, `VALUE_INDEX_IMPLEMENTATION.md`, `VALUE_INDEX_QUICKSTART.md`
- **Excel Upload**: `EXCEL_UPLOAD_FEATURE.md`, `EXCEL_UPLOAD_QUICKSTART.md`
- **Schema Sync**: `SCHEMA_SYNC_FEATURE.md`
- **Upload Progress**: `UPLOAD_PROGRESS_ENHANCEMENT.md`
- **Implementation Updates**: `IMPLEMENTATION_UPDATE_SUMMARY.md`
- **Navigation Prevention**: `NAVIGATION_PREVENTION_IMPLEMENTATION.md`

---

## Contributing
See implementation and update plans in the respective `.md` files for guidance on extending or modifying the agent.
npm run dev
```

The frontend will be available at `http://localhost:3600/`
The API will be available at `http://localhost:8100/`

## API Documentation

- Swagger UI: http://localhost:8100/docs
- ReDoc: http://localhost:8100/redoc

## Testing

```bash
python -m pytest tests/
```

## Architecture

- **Backend**: FastAPI with Python
- **Frontend**: React with TypeScript
- **Database**: Milvus vector database
- **Embeddings**: OpenAI text-embedding-3-small
- **LLM**: OpenAI GPT-4

## Key Components

- **Vector Store**: Manages embeddings for schema and few-shot examples
- **Discovery Service**: Finds relevant database schemas for queries
- **Generation Service**: Converts natural language to SQL
- **Admin Interface**: Manages few-shot examples and schema indexing
