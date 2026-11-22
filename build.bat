@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo          SYS-SENTINEL: Unified Build Pipeline
echo =======================================================

cd /d "%~dp0"

set "BUILD_EXE=1"
set "BUILD_INST=1"

if /i "%~1"=="--exe" (
    set "BUILD_INST=0"
)
if /i "%~1"=="--installer" (
    set "BUILD_EXE=0"
)

REM -------------------------------------------------------------
REM 1. BUILD EXECUTABLE (PyInstaller onedir distribution)
REM -------------------------------------------------------------
if "%BUILD_EXE%"=="1" (
    echo.
    echo [PHASE 1/2] Compiling SENTI.exe with PyInstaller...

    if not exist ".venv\Scripts\python.exe" (
        echo [ERROR] Virtual environment not found at .venv\Scripts\python.exe
        exit /b 1
    )

    REM Ensure PyInstaller is installed
    .\.venv\Scripts\python.exe -c "import PyInstaller" 2>nul
    if errorlevel 1 (
        echo [INFO] Installing PyInstaller from requirements-dev.txt...
        .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
        if errorlevel 1 (
            echo [ERROR] Failed to install PyInstaller.
            exit /b 1
        )
    )

    REM Generate multi-resolution application icon
    echo [INFO] Generating assets\senti.ico...
    .\.venv\Scripts\python.exe tools\make_icon.py
    if errorlevel 1 (
        echo [ERROR] Failed to generate icon.
        exit /b 1
    )

    REM Run PyInstaller compilation
    echo [INFO] Running PyInstaller with SENTI.spec...
    .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean SENTI.spec
    if errorlevel 1 (
        echo [ERROR] PyInstaller build failed.
        exit /b 1
    )

    echo [SUCCESS] Standalone distribution created in dist\SENTI\
)

REM -------------------------------------------------------------
REM 2. BUILD WINDOWS INSTALLER (Inno Setup)
REM -------------------------------------------------------------
if "%BUILD_INST%"=="1" (
    echo.
    echo [PHASE 2/2] Packaging Windows Setup Wizard...

    if not exist "dist\SENTI\SENTI.exe" (
        echo [ERROR] dist\SENTI\SENTI.exe not found. Build executable first.
        exit /b 1
    )

    set "ISCC="
    if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
        set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    ) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
        set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
    ) else (
        where iscc.exe >nul 2>&1
        if not errorlevel 1 (
            set "ISCC=iscc.exe"
        )
    )

    if "!ISCC!"=="" (
        echo [INFO] Inno Setup compiler ^(ISCC.exe^) not detected on PATH or Program Files.
        echo [INFO] To compile the setup wizard installer:
        echo        Run: winget install JRSoftware.InnoSetup
        echo        Then re-run: build.bat
    ) else (
        echo [INFO] Compiling installer with "!ISCC!"...
        "!ISCC!" installer.iss
        if errorlevel 1 (
            echo [ERROR] Inno Setup compilation failed.
            exit /b 1
        )
        echo [SUCCESS] Installer generated in dist\installer\
    )
)

echo.
echo =======================================================
echo [DONE] Build completed successfully.
echo =======================================================
