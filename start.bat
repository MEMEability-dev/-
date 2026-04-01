@echo off
chcp 65001 >nul 2>&1
title A股选股平台 v1.2

echo ================================
echo   A股选股平台 v1.2
echo ================================
echo.

where python3 >nul 2>&1
if %errorlevel% neq 0 (
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] 未找到 Python，请先安装 Python 3.10+
        pause
        exit /b 1
    )
    set PYTHON=python
) else (
    set PYTHON=python3
)

cd /d "%~dp0"

if not exist ".deps_installed" (
    echo [1/2] 安装依赖...
    %PYTHON% -m pip install -r requirements.txt -q
    echo. > .deps_installed
    echo   -^> 依赖安装完成
) else (
    echo [1/2] 依赖已安装，跳过
)

echo [2/2] 启动服务器...
echo.
echo   浏览器访问: http://localhost:8080
echo   按 Ctrl+C 停止服务
echo.

%PYTHON% app.py
pause
