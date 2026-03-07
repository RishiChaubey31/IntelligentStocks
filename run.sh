#!/bin/bash
cd "$(dirname "$0")"

echo "Starting AI Stock Agent..."
echo

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing backend dependencies..."
pip install -q -r requirements.txt

if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

echo
echo "Starting backend on http://127.0.0.1:8000"
echo "Starting frontend on http://localhost:5173"
echo

export PYTHONPATH="$(pwd)"
uvicorn backend.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

sleep 3

cd frontend && npm run dev &
FRONTEND_PID=$!

echo
echo "Both servers started. Open http://localhost:5173 in your browser."
echo "Press Ctrl+C to stop."
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
