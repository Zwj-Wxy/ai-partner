@echo off
chcp 936 >nul
title AI智能伴侣
cd /d "%~dp0"

if not exist "AI智能伴侣.exe" (
    echo [错误] 没有找到 AI智能伴侣.exe
    echo 请把本脚本放在 AI智能伴侣.exe 同一个文件夹里。
    pause
    exit /b 1
)

echo ==========================================
echo             AI 智能伴侣 启动器
echo ==========================================
echo.

tasklist /FI "IMAGENAME eq AI智能伴侣.exe" 2>nul | findstr /I "AI智能伴侣.exe" >nul
if not errorlevel 1 goto already

echo [1/2] 正在启动，第一次打开大约要 10 秒，请稍等...
echo       启动成功后会自动弹出一个独立窗口：没有地址栏、没有标签页，像个普通软件。
start "" "AI智能伴侣.exe"
timeout /t 10 /nobreak >nul

tasklist /FI "IMAGENAME eq AI智能伴侣.exe" 2>nul | findstr /I "AI智能伴侣.exe" >nul
if errorlevel 1 goto failed

echo [2/2] 启动成功，窗口应该已经出现了。
echo       如果只看到浏览器的普通标签页，说明浏览器正以【管理员权限】运行、拒绝新窗口，
echo       把浏览器窗口全部关掉，再双击一次本脚本就是独立窗口了。
goto tips

:already
echo [提示] 程序已经在运行了，不用重复启动。
echo       如果窗口被关掉了，双击本脚本会立刻把它重新弹出来。
goto tips

:failed
echo.
echo [失败] 程序没能启动起来。
echo        请双击 排查问题.bat，它会把原因写进 排查结果.txt，方便排查。
echo        如果窗口一闪就没了，可能是杀毒软件拦截，或者压缩包没解压完
echo        （必须解压整个文件夹，不能只拷 AI智能伴侣.exe，也不能在压缩包里直接运行）。
echo        也可以在命令行里运行 AI智能伴侣.exe，红色报错就是原因。

:tips
echo.
echo 说明：
echo   - 窗口左侧「API 设置」里粘贴 DeepSeek API Key，点「测试连接」确认可用
echo   - 勾选「记住到本机」，以后打开就不用再填了
echo   - 聊天记录自动保存在 sessions 文件夹，换电脑时一起拷走
echo   - 关掉窗口不等于退出：彻底退出请双击 停止AI智能伴侣.bat
echo.
pause
