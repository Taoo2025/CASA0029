# 在桌面创建"London PTAL 地图"快捷方式，指向 双击启动地图.bat
# 使用：右键 → "用 PowerShell 运行"，或在终端 powershell -File 创建桌面快捷方式.ps1

$ErrorActionPreference = "Stop"

$here       = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetBat  = Join-Path $here "双击启动地图.bat"
$iconSource = Join-Path $here "roundel\favicon.ico"   # 如果有就用，没有就用默认

if (-not (Test-Path $targetBat)) {
    Write-Error "找不到 $targetBat"
    exit 1
}

$desktop      = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "London PTAL 地图.lnk"

$wsh           = New-Object -ComObject WScript.Shell
$shortcut      = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath       = $targetBat
$shortcut.WorkingDirectory = $here
$shortcut.Description      = "London PTAL Resilience Map - 一键启动本地服务器并打开浏览器"
$shortcut.WindowStyle      = 1
if (Test-Path $iconSource) {
    $shortcut.IconLocation = $iconSource
}
$shortcut.Save()

Write-Host "✅ 已创建桌面快捷方式：$shortcutPath" -ForegroundColor Green
Write-Host "   双击它即可启动地图。" -ForegroundColor Green
