---
description: Start the SQL Agent application (backend, frontend, and Milvus)
---

# Start OctofyAgent Application

This workflow will start the OctofyAgent application with all required services.

## Prerequisites Check

1. Ensure Docker is running (required for OctofyAgent Milvus vector database)
2. Ensure you have a `.env` file with required configuration:
   - `OPENAI_API_KEY`
   - `SQL_SERVER_CONNECTION_STRING`
   - `API_KEY`

## Starting the Application

// turbo-all

3. Stop any existing containers
```bash
docker-compose down
```

4. Start OctofyAgent services (etcd, minio, milvus)
```bash
docker-compose up -d etcd minio milvus
```

5. Wait 15 seconds for OctofyAgent Milvus to initialize
```bash
timeout /t 15 /nobreak
```

6. Activate Python virtual environment and start backend
```bash
call .\myenv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

7. In a separate terminal, start the frontend (from the frontend directory)
```bash
cd frontend && npm run dev
```

## Verify Services

8. Check that all services are running:
   - **OctofyAgent Milvus**: `docker ps` should show octofyagent-etcd, octofyagent-minio, and octofyagent-milvus containers
   - **Backend API**: http://localhost:8100/docs (Swagger UI)
   - **Frontend**: http://localhost:3600

## Alternative: Use Quick Start Script

Alternatively, you can use the automated deployment script:

```bash
rebuild_and_deploy.bat
```

This will:
- Stop existing containers
- Start OctofyAgent services
- Start backend on port 8000
- Install frontend dependencies if needed
- Start frontend on port 3600

## Post-Start Tasks

- If this is a fresh installation, you may need to ingest metadata: `python scripts/ingest_metadata.py`
- Access the admin interface at http://localhost:3600/admin to manage schemas and few-shot examples
- Test a query at http://localhost:3600
