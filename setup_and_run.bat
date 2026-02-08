@echo off
title Nexus Wallet v3.2
echo.
echo   ╔══════════════════════════════════╗
echo   ║     Nexus Wallet v3.2 Setup      ║
echo   ╚══════════════════════════════════╝
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found!
    echo         Download from https://python.org
    echo         Make sure to check "Add to PATH" during install.
    pause & exit /b
)

echo [1/2] Installing dependencies from requirements.txt ...
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Some packages failed to install.
    echo          Try running manually: pip install -r requirements.txt
    echo          The wallet will still launch but some features may be limited.
    echo.
)

echo [2/2] Launching Nexus Wallet...
echo.
python main.py
pause
