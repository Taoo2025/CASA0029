# London PTAL Resilience Map - Startup Script (PowerShell)
# 更强大的启动脚本，包含错误诊断和恢复功能

$ErrorActionPreference = "Continue"
$WarningPreference = "Continue"

# 颜色定义
$colors = @{
    "Success" = "Green"
    "Error"   = "Red"
    "Warning" = "Yellow"
    "Info"    = "Cyan"
}

function Write-Header {
    param([string]$message)
    Write-Host "`n" + ("=" * 60) -ForegroundColor $colors["Info"]
    Write-Host $message -ForegroundColor $colors["Info"]
    Write-Host ("=" * 60) -ForegroundColor $colors["Info"]
}

function Write-Success {
    param([string]$message)
    Write-Host "✓ $message" -ForegroundColor $colors["Success"]
}

function Write-Error-Custom {
    param([string]$message)
    Write-Host "✗ $message" -ForegroundColor $colors["Error"]
}

function Write-Warning-Custom {
    param([string]$message)
    Write-Host "⚠ $message" -ForegroundColor $colors["Warning"]
}

function Write-Info {
    param([string]$message)
    Write-Host "ℹ $message" -ForegroundColor $colors["Info"]
}

# 初始化
Write-Header "London PTAL Resilience Map - Startup"

# 获取脚本所在目录
$scriptPath = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$projectRoot = Split-Path -Parent -Path $scriptPath

Write-Info "脚本位置: $scriptPath"
Write-Info "项目根目录: $projectRoot"

# 检查Python
Write-Info "`n检查Python环境..."
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Error-Custom "Python 未找到。请确保 Python 已安装并添加到 PATH"
    Write-Info "下载 Python: https://www.python.org/downloads/"
    Read-Host "按 Enter 键退出"
    exit 1
}

$pythonVersion = python --version 2>&1
Write-Success "Python 已安装: $pythonVersion"

# 检查虚拟环境
Write-Info "`n检查虚拟环境..."
$venvPath = Join-Path $projectRoot ".venv"
if (Test-Path "$venvPath\Scripts\Activate.ps1") {
    Write-Success "虚拟环境已找到"
    & "$venvPath\Scripts\Activate.ps1"
    Write-Success "虚拟环境已激活"
} else {
    Write-Warning-Custom "虚拟环境未找到: $venvPath"
    Write-Info "建议: 运行 'python -m venv .venv' 创建虚拟环境"
}

# 检查必要文件
Write-Info "`n检查必要文件..."
$requiredFiles = @(
    "London_PTAL_Accessibility_Map.html",
    "serve_range.py"
)

foreach ($file in $requiredFiles) {
    $filePath = Join-Path $scriptPath $file
    if (Test-Path $filePath) {
        Write-Success "找到: $file"
    } else {
        Write-Error-Custom "缺失: $file"
    }
}

# 检查数据文件夹
Write-Info "`n检查数据文件夹..."
$dataFolders = @("DATA", "data_chunks_osm_network", "grid_ai_chunks_osm_network")
foreach ($folder in $dataFolders) {
    $folderPath = Join-Path $scriptPath $folder
    if (Test-Path $folderPath) {
        Write-Success "找到: $folder"
    } else {
        Write-Warning-Custom "缺失: $folder"
    }
}

# 检查端口是否占用
Write-Info "`n检查端口..."
$port = 8080
$portInUse = $false

try {
    $netstat = netstat -ano 2>$null | Select-String ":$port "
    if ($netstat) {
        Write-Warning-Custom "端口 $port 已被占用"
        $portInUse = $true
    } else {
        Write-Success "端口 $port 可用"
    }
} catch {
    Write-Info "无法检查端口状态（跳过）"
}

if ($portInUse) {
    Write-Info "`n尝试杀死已有的进程..."
    try {
        $pid = ($netstat -split '\s+')[-1]
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        Write-Success "已杀死旧进程 (PID: $pid)"
        Start-Sleep -Seconds 2
    } catch {
        Write-Warning-Custom "无法杀死已有进程，请手动关闭"
    }
}

# 启动服务器
Write-Header "`n启动 HTTP 服务器..."
Write-Info "端口: $port"
Write-Info "URL: http://localhost:$port/London_PTAL_Accessibility_Map.html"

cd $scriptPath

$serverProcess = Start-Process python -ArgumentList "serve_range.py $port" `
    -PassThru `
    -WindowStyle Normal `
    -ErrorAction SilentlyContinue

if (-not $serverProcess) {
    Write-Error-Custom "无法启动服务器进程"
    Read-Host "按 Enter 键退出"
    exit 1
}

Write-Success "服务器进程已启动 (PID: $($serverProcess.Id))"

# 等待服务器启动
Write-Info "`n等待服务器启动..."
$maxRetries = 30
$retries = 0

while ($retries -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$port/London_PTAL_Accessibility_Map.html" `
            -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        
        if ($response.StatusCode -eq 200) {
            Write-Success "服务器已在线，返回 HTTP 200"
            break
        }
    } catch {
        $retries++
        if ($retries -lt $maxRetries) {
            Write-Host -NoNewline "."
            Start-Sleep -Seconds 1
        }
    }
}

if ($retries -eq $maxRetries) {
    Write-Warning-Custom "服务器可能未正常启动（超时）"
    Write-Info "您可以尝试手动访问: http://localhost:$port/London_PTAL_Accessibility_Map.html"
} else {
    Write-Success "连接成功！"
}

# 打开浏览器
Write-Info "`n打开浏览器..."
Start-Sleep -Seconds 1
Start-Process "http://localhost:$port/London_PTAL_Accessibility_Map.html" -ErrorAction SilentlyContinue

# 使用信息
Write-Header "启动完成"
Write-Host @"
✓ 服务器运行在: http://localhost:$port
✓ 进程 ID: $($serverProcess.Id)

故障排查:
  1. 如果页面显示"Failed to fetch"，请检查浏览器控制台 (F12)
  2. 确保所有数据文件存在于 $scriptPath
  3. 检查端口 $port 是否被其他程序占用
  4. 尝试在浏览器中刷新页面 (Ctrl+F5 清除缓存)

停止服务器:
  - 关闭这个 PowerShell 窗口，或
  - 按 Ctrl+C 停止

"@

# 保持窗口打开
Read-Host "`n按 Enter 键停止服务器并关闭"
Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
Write-Success "服务器已停止"
