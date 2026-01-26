# Backend Dockerfile for FastAPI (app/Dockerfile)
FROM python:3.11-slim

WORKDIR /app


# Install system dependencies for pyodbc and build tools
RUN apt-get update && \
    apt-get install -y gcc g++ unixodbc-dev curl gnupg2 && \
    # Install Microsoft ODBC Driver for SQL Server (no apt-key)
    curl -sSL https://packages.microsoft.com/keys/microsoft.asc -o /etc/apt/trusted.gpg.d/microsoft.asc && \
    curl -sSL https://packages.microsoft.com/config/debian/11/prod.list -o /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17 && \
    rm -rf /var/lib/apt/lists/*



# Copy root requirements.txt into backend image
COPY ../requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt



# Copy backend code as a package
COPY app ./app

# Expose FastAPI port
EXPOSE 8000

# Start FastAPI app (use app.main:app)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
