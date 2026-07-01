@echo off
chcp 65001 >nul
title BiyeMu - Toleo la Wavuti
cd /d "%~dp0"

echo.
echo  ============================================
echo    BiyeMu - Toleo la Wavuti (Browser)
echo  ============================================
echo.

python -m pip install flask -q 2>nul
python run_web.py

if errorlevel 1 (
    echo.
    echo  [!] Kuna tatizo. Jaribu: python -m pip install flask
    echo.
)

pause