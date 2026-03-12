@echo off
echo Starting AVP servers...

start "Backend" cmd /k "cd /d D:\royek\saas\backend && venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000"
start "Frontend" cmd /k "cd /d D:\royek\saas\frontend && npm run dev"

echo.
echo Backend : http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Both servers started in separate windows.
