<#
    AI智能伴侣 —— 安装到本机 / 卸载

    安装：powershell -NoProfile -ExecutionPolicy Bypass -File 安装到本机.ps1
    卸载：powershell -NoProfile -ExecutionPolicy Bypass -File 安装到本机.ps1 -Uninstall

    安装会做三件事（都只影响当前用户，不需要管理员权限）：
      1. 桌面放一个「AI智能伴侣」图标，双击直接打开（没有黑窗口）
      2. 开始菜单放一个「AI智能伴侣」
      3. 在「设置 → 应用 → 已安装的应用」里登记，可以像普通软件一样卸载

    卸载只删除图标和登记项，不删除这个文件夹（聊天记录在 sessions 里，由你自己决定留不留）。
#>
param([switch]$Uninstall, [string]$AppDir = $PSScriptRoot)

$ErrorActionPreference = "Stop"

$AppName    = "AI智能伴侣"
$AppVersion = "1.0.0"
$ExePath    = Join-Path $AppDir "AI智能伴侣.exe"
$IconPath   = Join-Path $AppDir "app.ico"
$RegPath    = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppName"
$DesktopLnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.lnk"
$StartLnk   = Join-Path ([Environment]::GetFolderPath("Programs")) "$AppName.lnk"

function Remove-Link([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        try { Remove-Item -LiteralPath $Path -Force; return $true } catch { return $false }
    }
    return $false
}

if ($Uninstall) {
    Write-Host "正在卸载「$AppName」..." -ForegroundColor Cyan
    $removed = 0
    if (Remove-Link $DesktopLnk) { $removed++ }
    if (Remove-Link $StartLnk)   { $removed++ }
    if (Test-Path -LiteralPath $RegPath) {
        Remove-Item -LiteralPath $RegPath -Recurse -Force
        Write-Host "  已删除「设置 → 应用」里的卸载项"
    }
    Write-Host "  已删除 $removed 个快捷方式"
    Write-Host ""
    Write-Host "卸载完成。程序文件还在：$AppDir" -ForegroundColor Green
    Write-Host "如果不需要了，直接把那个文件夹删掉即可。"
    exit 0
}

Write-Host "正在把「$AppName」安装到本机..." -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $ExePath)) {
    Write-Host ""
    Write-Host "没找到 AI智能伴侣.exe，安装中止。" -ForegroundColor Red
    Write-Host "请确认这个脚本和 AI智能伴侣.exe 在同一个文件夹里：$AppDir"
    exit 1
}

# 1 + 2. 桌面、开始菜单快捷方式
$shell = New-Object -ComObject WScript.Shell
$doneShortcut = 0
$deskFailed = $false
foreach ($lnkPath in @($DesktopLnk, $StartLnk)) {
    try {
        $lnk = $shell.CreateShortcut($lnkPath)
        $lnk.TargetPath       = $ExePath
        $lnk.WorkingDirectory = $AppDir
        $lnk.Description      = "$AppName —— 会记住你每一次聊天的 AI 伴侣"
        $lnk.WindowStyle      = 1
        if (Test-Path -LiteralPath $IconPath) {
            $lnk.IconLocation = "$IconPath,0"
        } else {
            $lnk.IconLocation = "$ExePath,0"
        }
        $lnk.Save()
        $doneShortcut++
        Write-Host "  已创建：$lnkPath"
    } catch {
        # 桌面被 OneDrive 重定向、或没有写权限时，不让整次安装失败
        if ($lnkPath -eq $DesktopLnk) { $deskFailed = $true }
        Write-Host "  [跳过] 这个位置建不了图标：$lnkPath" -ForegroundColor Yellow
        Write-Host "         $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

# 桌面快捷方式建不出来时退一步：直接在桌面放一个 .bat（不依赖 COM，普通写文件就行）
if ($deskFailed) {
    $fallback = Join-Path ([Environment]::GetFolderPath("Desktop")) "$AppName.bat"
    try {
        $srcBat = Join-Path $AppDir "启动AI智能伴侣.bat"
        if (Test-Path -LiteralPath $srcBat) {
            Copy-Item -LiteralPath $srcBat -Destination $fallback -Force
            $doneShortcut++
            Write-Host "  已改放一个启动文件到桌面：$fallback" -ForegroundColor Yellow
        }
    } catch { }
}

# 3. 卸载登记
$sizeKB = 0
try {
    $sum = (Get-ChildItem -LiteralPath $AppDir -Recurse -File -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
    if ($sum) { $sizeKB = [int]($sum / 1KB) }
} catch { }

try {
    if (-not (Test-Path -LiteralPath $RegPath)) {
        New-Item -Path $RegPath -Force | Out-Null
    }
    $uninstallCmd = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' +
                    (Join-Path $AppDir "安装到本机.ps1") + '" -Uninstall'
    Set-ItemProperty -Path $RegPath -Name "DisplayName"     -Value $AppName
    Set-ItemProperty -Path $RegPath -Name "DisplayVersion"  -Value $AppVersion
    Set-ItemProperty -Path $RegPath -Name "Publisher"       -Value "张维杰"
    Set-ItemProperty -Path $RegPath -Name "InstallLocation" -Value $AppDir
    Set-ItemProperty -Path $RegPath -Name "DisplayIcon"     -Value "$ExePath,0"
    Set-ItemProperty -Path $RegPath -Name "UninstallString" -Value $uninstallCmd
    Set-ItemProperty -Path $RegPath -Name "NoModify"        -Value 1 -Type DWord
    Set-ItemProperty -Path $RegPath -Name "NoRepair"        -Value 1 -Type DWord
    if ($sizeKB -gt 0) {
        Set-ItemProperty -Path $RegPath -Name "EstimatedSize" -Value $sizeKB -Type DWord
    }
    Write-Host "  已登记到「设置 → 应用 → 已安装的应用」"
    $doneShortcut++
} catch {
    # 注册表被组策略锁死等情况下，图标照样能用，不算失败
    Write-Host "  [跳过] 卸载登记没写成功，桌面图标不受影响" -ForegroundColor Yellow
    Write-Host "         $($_.Exception.Message)" -ForegroundColor DarkYellow
}

Write-Host ""
if ($doneShortcut -eq 0) {
    Write-Host "安装没成功 ❌" -ForegroundColor Red
    Write-Host "  桌面和开始菜单都没写进去（可能是权限或安全软件拦了）。"
    Write-Host "  退一步的办法：直接双击这个文件夹里的「启动AI智能伴侣.bat」，一样能用。"
    Write-Host "  想再试一次：右键「安装AI智能伴侣.bat」→ 以管理员身份运行。"
    exit 2
}

Write-Host "装好了 ✅" -ForegroundColor Green
Write-Host "  以后从桌面或开始菜单点「AI智能伴侣」就能用，不用再进这个文件夹。"
Write-Host "  想卸载：设置 → 应用 → 已安装的应用 → AI智能伴侣 → 卸载。"
exit 0
