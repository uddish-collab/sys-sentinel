@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo        SYS-SENTINEL: Building Windows Installer
echo =======================================================

cd /d "%~dp0"

REM 1. First ensure the onedir build exists in dist\SENTI
if not exist "dist\SENTI\SENTI.exe" (
    echo [INFO] dist\SENTI\SENTI.exe not found. Running build_exe.bat first...
    call build_exe.bat
    if errorlevel 1 (
        echo [ERROR] Failed to build executable.
        exit /b 1
    )
)

REM 2. Locate ISCC.exe (Inno Setup Compiler)
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

if "%ISCC%"=="" (
    echo [ERROR] Inno Setup Compiler (ISCC.exe) not found.
    echo Please install Inno Setup 6 from https://jrsoftware.org/isdl.php
    echo or run: winget install JRSoftware.InnoSetup
    exit /b 1
)

echo [INFO] Found Inno Setup at: "%ISCC%"
echo [INFO] Compiling installer.iss...

"%ISCC%" installer.iss

if errorlevel 1 (
    echo [ERROR] Inno Setup compilation failed.
    exit /b 1
)

echo =======================================================
echo [SUCCESS] Installer generated in dist\installer\
echo =======================================================
