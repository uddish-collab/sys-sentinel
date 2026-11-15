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

REM 4. Build single-file windowed executable
echo [INFO] Running PyInstaller...
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name SENTI --icon "assets\senti.ico" --paths "src" "src\senti_app.py"

if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    exit /b 1
)

echo =======================================================
echo [SUCCESS] SENTI.exe successfully built in dist\SENTI.exe
echo =======================================================
