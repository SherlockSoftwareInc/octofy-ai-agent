@echo off
echo Stopping existing containers...
docker-compose down

echo.
echo.
echo Starting Milvus containers...
docker-compose up -d etcd minio standalone
echo.
echo Waiting 15s for Milvus to start...
timeout /t 15 /nobreak

echo.
echo Starting Backend locally...
call .\myenv\Scripts\activate
start "SQL Agent Backend" uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

echo.
echo Starting Frontend locally...
cd frontend
if not exist node_modules (
    echo Installing frontend dependencies...
    call npm install
)
start "SQL Agent Frontend" npm run dev

echo.
echo Deployment complete.
echo Backend API: http://localhost:8000/docs
echo Frontend: http://localhost:45678

pause
