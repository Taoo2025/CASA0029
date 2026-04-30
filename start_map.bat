@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title London PTAL Map - Launcher

REM Switch to the directory of this script
cd /d "%~dp0"

echo ============================================
echo   London PTAL Resilience Map
echo   Double-click to launch. Close this window
echo   to stop the server.
echo ============================================
echo.

REM Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.x and add it to PATH.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Activate venv if present
if exist "..\.venv\Scripts\activate.bat" (
    call "..\.venv\Scripts\activate.bat" >nul 2>&1
)

REM Check required files
if not exist "London_PTAL_Accessibility_Map.html" (
    echo [ERROR] London_PTAL_Accessibility_Map.html not found.
    pause
    exit /b 1
)
if not exist "serve_range.py" (
    echo [ERROR] serve_range.py not found.
    pause
    exit /b 1
)

REM Find a free port (try 8080-8099)
set PORT=
for /l %%P in (8080,1,8099) do (
    if "!PORT!"=="" (
        netstat -ano | findstr ":%%P " | findstr "LISTENING" >nul 2>&1
        if errorlevel 1 set PORT=%%P
    )
)

if "%PORT%"=="" (
    echo [ERROR] No free port available in 8080-8099.
    pause
    exit /b 1
)

echo [INFO] Port  : %PORT%
echo [INFO] URL   : http://localhost:%PORT%/London_PTAL_Accessibility_Map.html
echo.
echo The browser will open automatically in a few seconds.
echo ====== Closing this window stops the server ======
echo.

REM Open the browser after a short delay (non-blocking)
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:%PORT%/London_PTAL_Accessibility_Map.html"

REM Run the server in the foreground; closing this window kills it
python serve_range.py %PORT%

echo.
echo Server stopped.
pause
