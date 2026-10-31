@echo off
chcp 936 >nul
title 创建桌面快捷方式
cd /d "%~dp0"

if not exist "AI智能伴侣.exe" (
    echo [错误] 请把本脚本放在 AI智能伴侣.exe 同一个文件夹里。
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0创建桌面快捷方式.ps1"
if errorlevel 1 (
    echo.
    echo [失败] 没能创建快捷方式，可以手动把「启动AI智能伴侣.bat」发送到桌面。
    pause
    exit /b 1
)

echo.
echo 完成：桌面上已经有「AI智能伴侣」图标了，以后双击它就能打开。
pause
