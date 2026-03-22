#!/bin/bash

# RealLink Ecosystem - Run Script
# Starts both backend (FastAPI) and frontend (Flask) servers

echo "=========================================="
echo "  RealLink Ecosystem - Starting Servers"
echo "=========================================="

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Kill any existing processes on ports 8000 and 5000
echo "Cleaning up existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:5000 | xargs kill -9 2>/dev/null || true

# Start Backend
echo ""
echo "Starting Backend (FastAPI on port 8000)..."
cd "$SCRIPT_DIR/backend"
source venv/bin/activate 2>/dev/null || pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to start
sleep 2

# Start Frontend
echo ""
echo "Starting Frontend (Flask on port 5000)..."
cd "$SCRIPT_DIR/frontend"
source venv/bin/activate 2>/dev/null || pip install -r requirements.txt
python app.py &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

echo ""
echo "=========================================="
echo "  RealLink Ecosystem is running!"
echo "=========================================="
echo ""
echo "Frontend: http://localhost:5000"
echo "Backend:  http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Wait for Ctrl+C
trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# Keep script running
wait
