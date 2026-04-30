# Create a "London PTAL Map" shortcut on the Desktop pointing at start_map.bat.
# Usage: right-click this file -> "Run with PowerShell",
#        or from a terminal:  powershell -File create_desktop_shortcut.ps1

$ErrorActionPreference = "Stop"

$here       = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetBat  = Join-Path $here "start_map.bat"
$iconSource = Join-Path $here "roundel\favicon.ico"   # 如果有就用，没有就用默认

if (-not (Test-Path $targetBat)) {
    Write-Error "找不到 $targetBat"
    exit 1
}

$desktop      = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "London PTAL Map.lnk"

$wsh           = New-Object -ComObject WScript.Shell
$shortcut      = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath       = $targetBat
$shortcut.WorkingDirectory = $here
$shortcut.Description      = "London PTAL Resilience Map - start local server and open in browser"
$shortcut.WindowStyle      = 1
if (Test-Path $iconSource) {
    $shortcut.IconLocation = $iconSource
}
$shortcut.Save()

Write-Host "Created desktop shortcut: $shortcutPath" -ForegroundColor Green
Write-Host "Double-click it to launch the map." -ForegroundColor Green
