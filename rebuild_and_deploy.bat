@echo off
echo Stopping existing containers...
docker-compose down

echo.
echo.
echo Starting OctofyAgent containers...
docker-compose up -d etcd minio milvus
echo.
echo Waiting 15s for OctofyAgent Milvus to start...
timeout /t 15 /nobreak

echo.
echo Starting Backend locally...
call .\myenv\Scripts\activate
start "OctofyAgent Backend" uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

echo.
echo Starting Frontend locally...
cd frontend
if not exist node_modules (
    echo Installing frontend dependencies...
    call npm install
)
start "OctofyAgent Frontend" npm run dev

echo.
echo Deployment complete.
echo Backend API: http://localhost:8100/docs
echo Frontend: http://localhost:3600

pause
