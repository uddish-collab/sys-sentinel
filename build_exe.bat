@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo          SYS-SENTINEL: Building SENTI.exe
echo =======================================================

cd /d "%~dp0"

REM 1. Verify virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
    exit /b 1
)

REM 2. Ensure PyInstaller is installed (dev-only)
.\.venv\Scripts\python.exe -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [INFO] Installing PyInstaller into .venv from requirements-dev.txt...
    .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller.
        exit /b 1
    )
)

REM 3. Generate multi-size transparent application icon
echo [INFO] Generating assets\senti.ico...
.\.venv\Scripts\python.exe tools\make_icon.py
if errorlevel 1 (
    echo [ERROR] Failed to generate icon.
    exit /b 1
)

REM 4. Build windowed directory distribution executable
echo [INFO] Running PyInstaller with SENTI.spec...
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean SENTI.spec

if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    exit /b 1
)

echo =======================================================
echo [SUCCESS] SENTI successfully built in dist\SENTI\
echo =======================================================
