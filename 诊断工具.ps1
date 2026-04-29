# 诊断脚本 - 检查"Failed to fetch"问题
# 用于排查地图加载数据失败的原因

$ErrorActionPreference = "Continue"

Write-Host "`n" + ("=" * 60) -ForegroundColor Cyan
Write-Host "London PTAL Map - Failed to Fetch 诊断工具" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan

$scriptPath = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition

# 1. 检查服务器是否运行
Write-Host "`n[1/6] 检查服务器状态..." -ForegroundColor Yellow

$serverRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8080/" -UseBasicParsing -TimeoutSec 3 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "✓ 服务器在线 (HTTP 200)" -ForegroundColor Green
        $serverRunning = $true
    } else {
        Write-Host "✗ 服务器返回异常状态码: $($response.StatusCode)" -ForegroundColor Red
    }
} catch {
    Write-Host "✗ 无法连接到服务器 (http://localhost:8080/)" -ForegroundColor Red
    Write-Host "  可能原因: 服务器未启动、端口不对、防火墙阻止" -ForegroundColor Gray
}

# 2. 检查主HTML文件
Write-Host "`n[2/6] 检查HTML文件..." -ForegroundColor Yellow

$htmlPath = Join-Path $scriptPath "London_PTAL_Accessibility_Map.html"
if (Test-Path $htmlPath) {
    $size = (Get-Item $htmlPath).Length / 1MB
    Write-Host "✓ HTML文件存在 (大小: $('{0:N2}' -f $size) MB)" -ForegroundColor Green
} else {
    Write-Host "✗ HTML文件不存在: $htmlPath" -ForegroundColor Red
}

# 3. 检查数据文件
Write-Host "`n[3/6] 检查数据文件..." -ForegroundColor Yellow

$dataFiles = @{
    "bus_routes_detailed.json" = "必需"
    "DATA/LSOA_simplified.geojson" = "可选"
    "DATA/PTAL_2023_Grid_100mx100m_Data.geojson" = "可选"
    "grid_to_lsoa.json" = "可选"
    "route_lines.geojson" = "可选"
    "data_manifest_osm_network.json" = "可选"
    "grid_ai_manifest_osm_network.json" = "可选"
}

$criticalMissing = $false
foreach ($file in $dataFiles.GetEnumerator()) {
    $path = Join-Path $scriptPath $file.Key
    $status = $file.Value
    
    if (Test-Path $path) {
        $size = (Get-Item $path).Length / 1MB
        Write-Host "✓ $($file.Key) ($('{0:N2}' -f $size) MB) [$status]" -ForegroundColor Green
    } else {
        if ($status -eq "必需") {
            Write-Host "✗ $($file.Key) [必需] - 缺失!" -ForegroundColor Red
            $criticalMissing = $true
        } else {
            Write-Host "⚠ $($file.Key) [可选] - 缺失" -ForegroundColor Yellow
        }
    }
}

# 4. 检查数据文件夹
Write-Host "`n[4/6] 检查数据文件夹..." -ForegroundColor Yellow

$folders = @{
    "DATA" = "可选"
    "data_chunks_osm_network" = "可选"
    "grid_ai_chunks_osm_network" = "可选"
}

foreach ($folder in $folders.GetEnumerator()) {
    $path = Join-Path $scriptPath $folder.Key
    
    if (Test-Path $path) {
        $fileCount = @(Get-ChildItem $path -Recurse -File).Count
        Write-Host "✓ $($folder.Key) (文件数: $fileCount) [$($folder.Value)]" -ForegroundColor Green
    } else {
        if ($folder.Value -eq "必需") {
            Write-Host "✗ $($folder.Key) [必需] - 缺失!" -ForegroundColor Red
            $criticalMissing = $true
        } else {
            Write-Host "⚠ $($folder.Key) [可选] - 缺失" -ForegroundColor Yellow
        }
    }
}

# 5. 测试文件下载
Write-Host "`n[5/6] 测试文件可下载性..." -ForegroundColor Yellow

if ($serverRunning) {
    $testFiles = @(
        "bus_routes_detailed.json",
        "route_lines.geojson",
        "London_LSOA_Centroids.geojson"
    )
    
    foreach ($file in $testFiles) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8080/$file" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            Write-Host "✓ $file (HTTP $($response.StatusCode))" -ForegroundColor Green
        } catch {
            if ($_.Exception.Response.StatusCode -eq 404) {
                Write-Host "✗ $file - 文件未找到 (HTTP 404)" -ForegroundColor Red
            } else {
                Write-Host "⚠ $file - 连接失败: $($_.Exception.Message)" -ForegroundColor Yellow
            }
        }
    }
} else {
    Write-Host "⚠ 服务器离线，跳过下载测试" -ForegroundColor Yellow
}

# 6. 检查CORS配置
Write-Host "`n[6/6] 检查CORS配置..." -ForegroundColor Yellow

if ($serverRunning) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8080/" -Method Options -UseBasicParsing -TimeoutSec 3
        $corsOrigin = $response.Headers["Access-Control-Allow-Origin"]
        
        if ($corsOrigin -eq "*") {
            Write-Host "✓ CORS已启用 (允许所有来源)" -ForegroundColor Green
        } elseif ($corsOrigin) {
            Write-Host "✓ CORS已启用 (允许: $corsOrigin)" -ForegroundColor Green
        } else {
            Write-Host "⚠ CORS头未设置" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "⚠ 无法检查CORS配置" -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠ 服务器离线，跳过CORS检查" -ForegroundColor Yellow
}

# 总结
Write-Host "`n" + ("=" * 60) -ForegroundColor Cyan
Write-Host "诊断报告" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan

if ($criticalMissing) {
    Write-Host "`n⚠ 发现关键文件缺失!" -ForegroundColor Red
    Write-Host "请确保所有必需文件都存在于:" -ForegroundColor Gray
    Write-Host "  $scriptPath" -ForegroundColor Gray
} elseif (-not $serverRunning) {
    Write-Host "`n⚠ 服务器未运行!" -ForegroundColor Red
    Write-Host "解决步骤:" -ForegroundColor Gray
    Write-Host "  1. 运行: 启动地图.bat 或 启动地图.ps1" -ForegroundColor Gray
    Write-Host "  2. 等待服务器启动（显示 'Serving' 消息）" -ForegroundColor Gray
    Write-Host "  3. 刷新浏览器页面 (Ctrl+F5)" -ForegroundColor Gray
} else {
    Write-Host "`n✓ 所有诊断项目正常!" -ForegroundColor Green
    Write-Host "建议:" -ForegroundColor Gray
    Write-Host "  1. 打开浏览器开发者工具 (F12)" -ForegroundColor Gray
    Write-Host "  2. 查看 Console 标签，了解具体错误" -ForegroundColor Gray
    Write-Host "  3. 查看 Network 标签，看哪些请求失败" -ForegroundColor Gray
    Write-Host "  4. 尝试清除浏览器缓存 (Ctrl+Shift+Del)" -ForegroundColor Gray
}

Write-Host "`n按 Enter 键退出..." -ForegroundColor Gray
Read-Host
