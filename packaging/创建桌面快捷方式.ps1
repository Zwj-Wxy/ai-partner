# 在桌面创建「AI智能伴侣」快捷方式（带自定义爱心图标）
# 由 创建桌面快捷方式.bat 调用，不要单独双击这个 ps1。

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

$target = Join-Path $root '启动AI智能伴侣.bat'
$icon = Join-Path $root 'app.ico'

if (-not (Test-Path -LiteralPath $target)) {
    Write-Host "找不到启动脚本：$target"
    exit 1
}
if (-not (Test-Path -LiteralPath $icon)) {
    $icon = Join-Path $root 'AI智能伴侣.exe'
}

$desktop = [Environment]::GetFolderPath('Desktop')
$linkPath = Join-Path $desktop 'AI智能伴侣.lnk'

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($linkPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = "$icon,0"
$shortcut.Description = 'AI 智能伴侣'
$shortcut.WindowStyle = 1
$shortcut.Save()

Write-Host "已创建快捷方式：$linkPath"
Write-Host "图标：$icon"
exit 0
