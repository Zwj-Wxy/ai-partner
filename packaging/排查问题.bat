@echo off
chcp 936 >nul
title AI智能伴侣 - 排查工具
cd /d "%~dp0"
set "LOG=排查结果.txt"
if exist "%LOG%" del "%LOG%"

echo ==========================================
echo        AI 智能伴侣 排查工具
echo ==========================================
echo.
echo 正在检查环境，大约需要 25 秒，请不要关窗口...
echo （检查完会自动打开一个 txt，把它发给作者即可）
echo.

>> "%LOG%" echo ============================================
>> "%LOG%" echo   AI 智能伴侣 排查结果
>> "%LOG%" echo ============================================
>> "%LOG%" echo.
>> "%LOG%" echo [1] 系统版本
>> "%LOG%" ver
>> "%LOG%" echo.

set "EXE=缺"
if exist "AI智能伴侣.exe" set "EXE=有"
set "INT=缺"
if exist "_internal" set "INT=有"
set "PYDLL=缺"
if exist "_internal\python313.dll" set "PYDLL=有"
set "STATIC=缺"
if exist "_internal\streamlit\static\index.html" set "STATIC=有"
set "OA=缺"
if exist "_internal\openai\__init__.py" set "OA=有"

>> "%LOG%" echo [2] 文件是否齐全
>> "%LOG%" echo     AI智能伴侣.exe        : %EXE%
>> "%LOG%" echo     _internal 文件夹      : %INT%
>> "%LOG%" echo     python313.dll         : %PYDLL%
>> "%LOG%" echo     streamlit 前端文件    : %STATIC%
>> "%LOG%" echo     openai 模块           : %OA%
>> "%LOG%" echo.
>> "%LOG%" echo     说明：_internal 显示"缺"，就是只拷了 exe 或没解压完整，这样必然打不开。
>> "%LOG%" echo.

>> "%LOG%" echo [3] 8501 端口占用情况（下面有行就说明端口被别人占了）
netstat -ano | findstr ":8501" >> "%LOG%" 2>&1
>> "%LOG%" echo.

>> "%LOG%" echo [4] 启动测试（最多等 20 秒）
echo 正在启动程序，请稍等 20 秒...
start "" "AI智能伴侣.exe"
timeout /t 20 /nobreak >nul
tasklist /FI "IMAGENAME eq AI智能伴侣.exe" 2>nul | findstr /I "AI智能伴侣.exe" >nul
if errorlevel 1 set "RUN=没有在运行（启动失败）"
if not errorlevel 1 set "RUN=在运行"
>> "%LOG%" echo     程序进程：%RUN%
>> "%LOG%" echo.

if not exist "启动日志.txt" goto nolog
>> "%LOG%" echo [5] 启动日志.txt 的内容
type "启动日志.txt" >> "%LOG%"
>> "%LOG%" echo.
:nolog

>> "%LOG%" echo ============================================
>> "%LOG%" echo   把上面全部内容发给作者，就能定位问题。
>> "%LOG%" echo ============================================

echo.
echo 检查完毕，正在打开 %LOG% ...
start "" notepad "%LOG%"
echo.
pause
