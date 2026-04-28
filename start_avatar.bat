@echo off
REM ============================================
REM Quick Start AVATAR Application
REM ============================================

echo.
echo ========================================
echo   Starting AVATAR Tsunami System
echo ========================================
echo.

REM Step 1: Start Docker Containers
echo [1/2] Starting Docker containers...
cd /d "%~dp0"
docker-compose up -d

REM Wait for containers to be ready
echo.
echo Waiting for containers to start (15 seconds)...
timeout /t 15 /nobreak

REM Step 2: Start Frontend
echo.
echo [2/2] Starting Frontend dev server...
cd /d "%~dp0..\FrontendSkripsi"
start cmd /k "npm run dev"

REM Done
echo.
echo ========================================
echo   AVATAR Started Successfully!
echo ========================================
echo.
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8001
echo pgAdmin:  http://localhost:5051
echo.
echo Press any key to open browser...
pause >nul
start http://localhost:3000

exit
