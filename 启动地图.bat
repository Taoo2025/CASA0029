@echo off
setlocal enabledelayedexpansion

REM 获取脚本所在目录
cd /d "%~dp0"

REM 获取项目根目录（上一级）
for /d %%A in (..) do set "PROJECT_ROOT=%%~fA"

echo ============================================
echo London PTAL Resilience Map - Startup Script
echo ============================================
echo.

REM 检查Python是否可用
where python >nul 2>&1
if !errorlevel! neq 0 (
    echo Error: Python not found in PATH
    echo Please ensure Python is installed and added to PATH
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查虚拟环境
if exist "%PROJECT_ROOT%\.venv\Scripts\activate.bat" (
    echo Activating Python virtual environment...
    call "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
    echo Virtual environment activated.
) else (
    echo Warning: Virtual environment not found at %PROJECT_ROOT%\.venv
    echo Consider running: python -m venv .venv
)

echo.
echo Checking for required files...

REM 检查主HTML文件
if not exist "London_PTAL_Accessibility_Map.html" (
    echo Error: London_PTAL_Accessibility_Map.html not found
    pause
    exit /b 1
)

REM 检查serve_range.py
if not exist "serve_range.py" (
    echo Error: serve_range.py not found
    pause
    exit /b 1
)

echo Main files: OK
echo Data folders: 
if exist "DATA" echo   - DATA: found
if exist "data_chunks_osm_network" echo   - data_chunks_osm_network: found
if exist "grid_ai_chunks_osm_network" echo   - grid_ai_chunks_osm_network: found

echo.
echo Starting HTTP server on port 8080...
echo Current directory: %cd%
echo URL: http://localhost:8080/London_PTAL_Accessibility_Map.html
echo.

REM 启动服务器
start "London PTAL Map Server (Close to Stop)" cmd /k "python serve_range.py 8080 && pause"

REM 等待服务器启动
echo Waiting for server to start (5 seconds)...
timeout /t 5 /nobreak > nul

REM 打开浏览器
echo Opening browser...
start "" "http://localhost:8080/London_PTAL_Accessibility_Map.html"

echo.
echo ============================================
echo Server is starting in the background.
echo
echo If you see "Failed to fetch" errors:
echo   1. Check browser console (F12) for detailed errors
echo   2. Ensure all data files are present
echo   3. Try refreshing the page (Ctrl+F5)
echo   4. Check that port 8080 is not in use
echo
echo To stop the server, close the "London PTAL Map Server" window.
echo ============================================
echo.

REM 如果你想使用PowerShell版本（更好的诊断），可以取消注释下面的行:
REM powershell -ExecutionPolicy Bypass -File "启动地图.ps1"

exit /b 0
