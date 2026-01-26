#!/bin/bash

# Configuration
APP_MODULE="app.main:app"
PORT=8000
VENV_PATH="./venv"

echo "--- Starting Deployment ---"

# 1. Stop the old process
echo "Stopping old backend..."
sudo pkill -f "uvicorn $APP_MODULE" || echo "No existing process found."

# 2. Activate Virtual Environment
if [ -d "$VENV_PATH" ]; then
    echo "Activating virtual environment..."
    source "$VENV_PATH/bin/activate"
else
    echo "Virtual environment not found. Creating one..."
    python3 -m venv venv
    source venv/bin/activate
fi

# 3. Install/Update dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Start the new process in the background
echo "Starting Uvicorn on port $PORT..."
nohup uvicorn $APP_MODULE --host 0.0.0.0 --port $PORT > log.txt 2>&1 &

echo "--- Deployment Complete ---"
echo "Check logs with: tail -f log.txt"