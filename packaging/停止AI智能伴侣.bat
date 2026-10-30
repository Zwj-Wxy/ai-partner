@echo off
chcp 65001 >nul
title 停止 AI智能伴侣

echo 正在结束 AI智能伴侣.exe ...
taskkill /IM "AI智能伴侣.exe" /F >nul 2>&1

if %errorlevel%==0 (
    echo 已停止。
) else (
    echo 程序本来就没在运行。
)

timeout /t 2 /nobreak >nul
