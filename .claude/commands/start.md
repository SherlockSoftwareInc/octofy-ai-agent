---
description: Start both backend and frontend services for the SQL Agent application
---

# Start Development Servers

This command starts both the backend (FastAPI) and frontend (Vite) development servers.

## Steps

1. **Start the backend server** in a terminal:
   ```bash
   cd /d $WORKSPACE && call myenv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Start the frontend server** in a separate terminal:
   ```bash
   cd /d $WORKSPACE\frontend && npm run dev
   ```

3. **Confirm services are running** and inform the user:
   - Backend API: http://localhost:8000
   - Frontend: http://localhost:45678
   - API Docs: http://localhost:8000/docs

## Notes

- The backend runs on **port 8000** using uvicorn with hot-reload enabled
- The frontend runs on **port 45678** using Vite dev server
- Start the backend first to ensure API is available when frontend loads
- Both servers run in watch mode for development
