@echo off
chcp 936 >nul
title AI智能伴侣
cd /d "%~dp0"

if not exist "AI智能伴侣.exe" (
    echo [错误] 没有找到 AI智能伴侣.exe
    echo 请把本脚本放在与 AI智能伴侣.exe 同一个文件夹里。
    pause
    exit /b 1
)

echo ==========================================
echo             AI 智能伴侣 启动器
echo ==========================================
echo.
echo [1/2] 正在启动程序，首次启动大约需要 10 秒...
start "" "AI智能伴侣.exe"

echo [2/2] 稍后自动打开浏览器：http://localhost:8501
timeout /t 8 /nobreak >nul
start "" http://localhost:8501

echo.
echo 说明：
echo   - 浏览器没自动打开，就手动访问 http://localhost:8501
echo   - 第一次使用请在页面左侧填写 DeepSeek API Key
echo   - 关闭这个窗口不会退出程序，想彻底退出请双击「停止AI智能伴侣.bat」
echo.
pause
