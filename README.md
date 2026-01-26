# SQL Agent

A database AI agent that helps users query databases using natural language.

## Setup

### Prerequisites

- Python 3.8+
- Node.js 16+
- Docker (for Milvus database)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd sql-agent2
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

4. **Start Milvus Database**
   ```bash
   docker-compose up -d
   ```

5. **Initialize Milvus Collections**
   ```bash
   python scripts/ingest_metadata.py
   ```

6. **Configure Environment (Optional)**
   Create a `.env` file with your settings:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   SQL_SERVER_CONNECTION_STRING=your_database_connection_string
   ```

## Running the Application

### Backend API
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

### Frontend
```bash
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:45678/`
The API will be available at `http://localhost:5000/`

## API Documentation

- Swagger UI: http://localhost:5000/docs
- ReDoc: http://localhost:5000/redoc

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
