# 编译「AI伴侣窗口.exe」——一个最小的 WebView2 窗口宿主。
#
# 为什么不用 pywebview：pythonnet 在 PyInstaller 打包后会加载 .NET 运行时失败；
# 这个小宿主只用 .NET Framework 自带的 WinForms + WebView2，几十 KB，稳得多。
#
# 产物（默认写到 assets\window_host\）：
#   AI伴侣窗口.exe
#   Microsoft.Web.WebView2.Core.dll
#   Microsoft.Web.WebView2.WinForms.dll
#   WebView2Loader.dll
#
# 用法：powershell -ExecutionPolicy Bypass -File scripts\build_window_host.ps1
param(
    [string]$Python = "",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $root "assets\window_host" }

$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) {
    $csc = Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319\csc.exe"
}
if (-not (Test-Path $csc)) {
    Write-Host "[跳过] 这台机器没有 .NET Framework 编译器（csc.exe），不编译窗口宿主。" -ForegroundColor Yellow
    exit 0
}

# 找 pywebview 自带的 WebView2 托管 DLL（免装 NuGet / VS）
if (-not $Python) {
    foreach ($candidate in @(
        (Join-Path $root ".venv\Scripts\python.exe"),
        "D:\Python-Project\py_project01\.venv\Scripts\python.exe",
        "python"
    )) {
        if ($candidate -eq "python" -or (Test-Path $candidate)) { $Python = $candidate; break }
    }
}

$libDir = $null
try {
    $sitePackages = & $Python -c "import webview, os; print(os.path.dirname(webview.__file__))" 2>$null
    if ($LASTEXITCODE -eq 0 -and $sitePackages) {
        $candidate = Join-Path (Split-Path -Parent $sitePackages) "webview\lib"
        if (Test-Path $candidate) { $libDir = $candidate }
    }
} catch {
    Write-Host "[警告] 没能用 Python 定位 pywebview：$_" -ForegroundColor Yellow
}
if (-not $libDir) {
    foreach ($candidate in @(
        "D:\Python-Project\py_project01\.venv\Lib\site-packages\webview\lib",
        (Join-Path $root "dist\AI智能伴侣\_internal\webview\lib")
    )) {
        if (Test-Path $candidate) { $libDir = $candidate; break }
    }
}
if (-not $libDir) {
    Write-Host "[跳过] 找不到 webview\lib（先 pip install pywebview），不编译窗口宿主。" -ForegroundColor Yellow
    exit 0
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$coreDll = Join-Path $libDir "Microsoft.Web.WebView2.Core.dll"
$winFormsDll = Join-Path $libDir "Microsoft.Web.WebView2.WinForms.dll"
$loader = Join-Path $libDir "runtimes\win-x64\native\WebView2Loader.dll"
foreach ($need in @($coreDll, $winFormsDll, $loader)) {
    if (-not (Test-Path $need)) {
        Write-Host "[跳过] 缺少 $need" -ForegroundColor Yellow
        exit 0
    }
}

$exe = Join-Path $OutDir "AI伴侣窗口.exe"
Write-Host "正在编译 $exe ..."
& $csc /nologo /target:winexe /optimize+ "/out:$exe" `
    "/r:$coreDll" "/r:$winFormsDll" `
    /r:System.Windows.Forms.dll /r:System.Drawing.dll `
    (Join-Path $root "window_host\WindowHost.cs")
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $exe)) {
    throw "编译窗口宿主失败（csc 退出码 $LASTEXITCODE）"
}

Copy-Item $coreDll (Join-Path $OutDir "Microsoft.Web.WebView2.Core.dll") -Force
Copy-Item $winFormsDll (Join-Path $OutDir "Microsoft.Web.WebView2.WinForms.dll") -Force
Copy-Item $loader (Join-Path $OutDir "WebView2Loader.dll") -Force

Write-Host "[完成] 窗口宿主：" -NoNewline
Get-ChildItem $OutDir | ForEach-Object { Write-Host (" " + $_.Name + " (" + $_.Length + "B)") -NoNewline }
Write-Host ""
