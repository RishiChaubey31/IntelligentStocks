@echo off
cd /d "%~dp0"

echo Starting AI Stock Agent...
echo.

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing backend dependencies...
pip install -q -r requirements.txt

if not exist "frontend\node_modules" (
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)

echo.
echo Starting backend on http://127.0.0.1:8001
echo Starting frontend on http://localhost:5173
echo.

start "Backend" cmd /k "cd /d %~dp0 && set PYTHONPATH=%CD% && venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001"

timeout /t 3 /nobreak > nul

start "Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo Both servers started. Open http://localhost:5173 in your browser.
echo Press any key to exit (servers will keep running in separate windows).
pause > nul
