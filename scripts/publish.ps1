# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    把 AI 智能伴侣 推到 GitHub（含自动打 tag 让 CI 打 Release）。

.DESCRIPTION
    先手动在网页上建一个**空仓库**（不要勾选 README / .gitignore / License），
    然后在本目录执行：

        powershell -ExecutionPolicy Bypass -File scripts\publish.ps1 -RepoUrl https://github.com/你的用户名/ai-partner.git

    只想先推代码、不触发 Release：

        ... -SkipTag

    只演练不真推：

        ... -WhatIf

.NOTES
    认证二选一（第一次 push 会要求登录）：
      A. HTTPS：用户名填 GitHub 用户名，密码填 Personal Access Token（不是登录密码）
      B. SSH  ：git remote set-url origin git@github.com:用户名/仓库名.git
               并把 %USERPROFILE%\.ssh\id_ed25519.pub 加到 GitHub 的 SSH keys
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoUrl,

    [string]$Tag = "v1.0.0",

    [switch]$SkipTag,

    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "    " + $text -ForegroundColor Green }
function Warn($text) { Write-Host "    " + $text -ForegroundColor Yellow }

# ---------------------------------------------------------------- 基本检查
Step "检查仓库状态"
if (-not (Test-Path ".git")) {
    throw "当前目录不是 git 仓库：$root"
}
$dirty = git status --porcelain
if ($dirty) {
    Warn "有未提交的改动，先提交再发布："
    $dirty | ForEach-Object { Warn "  $_" }
    throw "工作区不干净，已中止。"
}
$branch = (git branch --show-current).Trim()
$commits = (git rev-list --count HEAD).Trim()
Ok "分支 $branch，共 $commits 个提交，工作区干净"

# 防止把几百 MB 的产物推上去（GitHub 单文件上限 100 MB）
Step "检查有没有误提交大文件"
$big = git ls-files | ForEach-Object {
    $f = Get-Item $_ -ErrorAction SilentlyContinue
    if ($f -and $f.Length -gt 10MB) { $f }
}
if ($big) {
    $big | ForEach-Object { Warn ("{0}  {1:N1} MB" -f $_.Name, ($_.Length / 1MB)) }
    throw "上面这些文件超过 10 MB，不应该进仓库（本该被 .gitignore 忽略）。"
}
Ok "没有大文件，仓库很小"

# ---------------------------------------------------------------- 配置 remote
Step "设置 origin"
$existing = git remote
if ($existing -contains "origin") {
    $old = (git remote get-url origin).Trim()
    if ($old -ne $RepoUrl) {
        Warn "origin 原来是 $old，改成 $RepoUrl"
        if (-not $WhatIf) { git remote set-url origin $RepoUrl }
    }
    else {
        Ok "origin 已经是 $RepoUrl"
    }
}
else {
    if (-not $WhatIf) { git remote add origin $RepoUrl }
    Ok "已添加 origin -> $RepoUrl"
}

# 本机走 https 时需要 openssl 后端，schannel 会报 SEC_E_NO_CREDENTIALS
if ($RepoUrl -like "https://*") {
    if (-not $WhatIf) { git config http.sslBackend openssl }
    Ok "已设置 http.sslBackend=openssl（本机 schannel 在这台机器上会失败）"
}

# ---------------------------------------------------------------- 推代码
Step "推送 $branch"
if ($WhatIf) {
    Warn "[演练] git push -u origin $branch"
}
else {
    git push -u origin $branch
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Warn "推送失败，多半是没通过认证。两种办法："
        Warn "  A. HTTPS：用户名填 GitHub 用户名，密码填 Personal Access Token"
        Warn "     （Settings → Developer settings → Personal access tokens → repo 权限）"
        Warn "  B. SSH  ：git remote set-url origin git@github.com:用户名/仓库名.git"
        Warn "     并把 $env:USERPROFILE\.ssh\id_ed25519.pub 的内容加到 GitHub → Settings → SSH and GPG keys"
        throw "推送失败。"
    }
    Ok "代码已推上去"
}

# ---------------------------------------------------------------- 发 Release
if ($SkipTag) {
    Step "跳过打 tag"
    Warn "没打 tag 就不会有 Release。想手动发：把 AI-Partner-Windows-x64.zip 上传到 Releases 页面。"
}
else {
    Step "打 tag $Tag 并推送（触发 CI 自动打包）"
    $tagExists = (git tag -l $Tag)
    if ($tagExists) {
        Warn "本地已有 tag $Tag，先删掉重建，指向最新提交"
        if (-not $WhatIf) { git tag -d $Tag | Out-Null }
    }
    if ($WhatIf) {
        Warn "[演练] git tag $Tag / git push origin $Tag"
    }
    else {
        git tag $Tag
        git push origin $Tag
        if ($LASTEXITCODE -ne 0) { throw "推送 tag 失败。" }
        Ok "tag $Tag 已推送"
    }
}

# ---------------------------------------------------------------- 结尾提示
Step "下一步"
$web = $RepoUrl -replace "\.git$", ""
Ok "仓库首页：     $web"
Ok "Actions（看打包进度）：$web/actions"
if (-not $SkipTag -and -not $WhatIf) {
    Ok "Release 页（等 CI 打完）：$web/releases"
    Warn "CI 大约 5~8 分钟：Build → Bundle check（含 exe 自检）→ App test → Launch check → 发 Release"
    Warn "如果 CI 失败，日志里搜 'Bundle check' 或 'Launch check' 那一步。"
}
Write-Host ""
