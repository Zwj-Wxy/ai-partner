# 一键打包 AI 智能伴侣为 Windows 绿色版
# 用法： powershell -ExecutionPolicy Bypass -File scripts\build.ps1
# 参数： -SkipInstall 跳过创建虚拟环境/安装依赖   -NoZip 不生成 zip

[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$NoZip
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "==> 项目目录: $root" -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "没有找到 python，请先安装 Python 3.11+ 并勾选 Add to PATH"
}

$venvPython = Join-Path $root '.venv\Scripts\python.exe'

# 1. 虚拟环境 + 依赖
if (-not $SkipInstall) {
    if (-not (Test-Path $venvPython)) {
        Write-Host "==> 创建虚拟环境 .venv" -ForegroundColor Cyan
        python -m venv .venv
    }
    Write-Host "==> 安装依赖（首次较慢）" -ForegroundColor Cyan
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements-build.txt
}

if (-not (Test-Path $venvPython)) { $venvPython = 'python' }

# 2. 语法检查
Write-Host "==> 语法检查" -ForegroundColor Cyan
& $venvPython -m py_compile app.py launcher.py

# 3. 清理旧产物并打包
Write-Host "==> PyInstaller 打包（约 1-3 分钟）" -ForegroundColor Cyan
if (Test-Path 'build') { Remove-Item 'build' -Recurse -Force }
if (Test-Path 'dist') { Remove-Item 'dist' -Recurse -Force }

& $venvPython -m PyInstaller --noconfirm --clean app.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }

# 4. 附带启动脚本与说明书
$outDir = Join-Path $root 'dist\AI智能伴侣'
Copy-Item (Join-Path $root 'packaging\*.bat') $outDir -Force
Copy-Item (Join-Path $root 'docs\使用说明.md') $outDir -Force

# 5. 压缩
if (-not $NoZip) {
    $zip = Join-Path $root 'AI-Partner-Windows-x64.zip'
    if (Test-Path $zip) { Remove-Item $zip -Force }
    Write-Host "==> 压缩为 $zip" -ForegroundColor Cyan
    if (Get-Command 7z.exe -ErrorAction SilentlyContinue) {
        7z a -tzip $zip "$outDir\" -mx=5 | Out-Null
    } else {
        Compress-Archive -Path $outDir -DestinationPath $zip -CompressionLevel Optimal
    }
}

# 6. 汇总
$sizeMB = [math]::Round(((Get-ChildItem $outDir -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host ""
Write-Host "==> 完成！产物目录: $outDir （$sizeMB MB）" -ForegroundColor Green
Get-ChildItem $outDir | Select-Object Mode, Length, Name | Format-Table -AutoSize
Write-Host "双击 dist\AI智能伴侣\启动AI智能伴侣.bat 即可运行" -ForegroundColor Green
