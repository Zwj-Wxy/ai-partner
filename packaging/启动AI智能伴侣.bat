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

tasklist /FI "IMAGENAME eq AI智能伴侣.exe" 2>nul | findstr /I "AI智能伴侣.exe" >nul
if not errorlevel 1 goto already

echo [1/2] 正在启动，首次启动大约需要 10 秒...
echo       启动后浏览器会自动打开，不用手动输入网址。
start "" "AI智能伴侣.exe"
timeout /t 10 /nobreak >nul

tasklist /FI "IMAGENAME eq AI智能伴侣.exe" 2>nul | findstr /I "AI智能伴侣.exe" >nul
if errorlevel 1 goto failed

echo [2/2] 启动成功，浏览器里应该已经出现「AI智能伴侣」页面了。
goto tips

:already
echo [提示] 程序已经在运行了，不用重复启动。
echo        请直接看浏览器里的页面；如果浏览器没打开，双击「停止AI智能伴侣.bat」再启动一次。
goto tips

:failed
echo.
echo [失败] 程序没能启动起来。
echo        请双击「排查问题.bat」，它会生成一份 排查结果.txt，把那个文件发给作者。
echo        如果窗口闪一下就没了，多半是杀毒软件拦截，或解压不完整（_internal 文件夹必须在）。

:tips
echo.
echo 说明：
echo   - 页面左侧「API 设置」里粘贴 DeepSeek API Key，点「测试连接」确认可用
echo   - 关闭这个窗口不会退出程序，想彻底退出请双击「停止AI智能伴侣.bat」
echo.
pause
