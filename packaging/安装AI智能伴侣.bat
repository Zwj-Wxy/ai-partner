@echo off
chcp 936 >nul
title 安装 AI智能伴侣
echo.
echo   正在把「AI智能伴侣」安装到本机...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0安装到本机.ps1"
echo.
echo   以后从桌面图标或开始菜单打开「AI智能伴侣」就行，
echo   不用再进这个文件夹，也不会再有黑窗口。
echo.
pause
