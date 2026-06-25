@echo off
chcp 65001 >nul 2>&1
title VideoMatrix
cd /d "%~dp0"

echo ================================
echo   Video Matrix System
echo ================================
echo.

echo [1/4] Checking Python...
python --version 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo Please install Python 3.11 from https://www.python.org/
    echo.
    pause
    exit /b 1
)

echo [2/4] Checking PyQt6...
python -c "import PyQt6; print('PyQt6 OK')" 2>&1
if %errorlevel% neq 0 (
    echo Installing PyQt6...
    pip install PyQt6 -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo [3/4] Checking PyQt6-WebEngine...
python -c "import PyQt6.QtWebEngineWidgets; print('WebEngine OK')" 2>&1
if %errorlevel% neq 0 (
    echo Installing PyQt6-WebEngine...
    pip install PyQt6-WebEngine -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo [4/4] Checking requests...
python -c "import requests; print('requests OK')" 2>&1
if %errorlevel% neq 0 (
    echo Installing requests...
    pip install requests -i https://pypi.tuna.tsinghua.edu.cn/simple
)

echo.
echo All dependencies OK. Starting...
echo.
python main.py

echo.
echo Program exited.
pause
