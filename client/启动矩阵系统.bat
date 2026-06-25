@echo off
chcp 65001 >nul 2>&1
title 矩阵运营系统

echo 正在检查依赖...

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.11+
    pause
    exit /b 1
)

:: 检查并安装依赖
pip show PyQt6 >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装 PyQt6...
    pip install PyQt6 -i https://pypi.tuna.tsinghua.edu.cn/simple
)

pip show PyQt6-WebEngine >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装 PyQt6-WebEngine...
    pip install PyQt6-WebEngine -i https://pypi.tuna.tsinghua.edu.cn/simple
)

pip show requests >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装 requests...
    pip install requests -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo 启动中...
cd /d "%~dp0"
python main.py
if %errorlevel% neq 0 (
    echo.
    echo 程序异常退出
    pause
)
