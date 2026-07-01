@echo off
chcp 65001 >nul
title Mfumo wa BiyeMu
cd /d "%~dp0"

echo.
echo  ============================================
echo    Mfumo wa Kudhibiti Maduka ya BiyeMu
echo  ============================================
echo.
echo  Inaanza programu...
echo.

python main.py

if errorlevel 1 (
    echo.
    echo  [!] Kuna tatizo. Jaribu kufungua PowerShell na uandike:
    echo      cd "%~dp0"
    echo      python main.py
    echo.
)

pause