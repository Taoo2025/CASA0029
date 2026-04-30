@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title London PTAL Map - 双击启动

REM 切到脚本所在目录
cd /d "%~dp0"

echo ============================================
echo   London PTAL Resilience Map
echo   双击启动 - 关闭本窗口即停止服务
echo ============================================
echo.

REM 检查 Python
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.x 并加入 PATH
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 激活虚拟环境（如果存在）
if exist "..\.venv\Scripts\activate.bat" (
    call "..\.venv\Scripts\activate.bat" >nul 2>&1
)

REM 检查必需文件
if not exist "London_PTAL_Accessibility_Map.html" (
    echo [错误] 找不到 London_PTAL_Accessibility_Map.html
    pause
    exit /b 1
)
if not exist "serve_range.py" (
    echo [错误] 找不到 serve_range.py
    pause
    exit /b 1
)

REM 自动寻找一个空闲端口（8080 起，最多试到 8099）
set PORT=
for /l %%P in (8080,1,8099) do (
    if "!PORT!"=="" (
        netstat -ano | findstr ":%%P " | findstr "LISTENING" >nul 2>&1
        if errorlevel 1 set PORT=%%P
    )
)

if "%PORT%"=="" (
    echo [错误] 8080-8099 端口都被占用，请关闭其他服务后重试
    pause
    exit /b 1
)

echo [启动] 端口: %PORT%
echo [地址] http://localhost:%PORT%/London_PTAL_Accessibility_Map.html
echo.
echo 浏览器会在几秒后自动打开。
echo ====== 关闭本窗口 = 停止服务器 ======
echo.

REM 5 秒后用浏览器打开（后台等待，不阻塞服务器启动）
start "" /b cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:%PORT%/London_PTAL_Accessibility_Map.html"

REM 在前台运行 server，关闭本窗口即终止
python serve_range.py %PORT%

echo.
echo 服务器已停止。
pause
