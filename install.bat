@echo off
setlocal enabledelayedexpansion

set "REQUIRED_VERSION=3.12.10"
set "PYTHON_URL=https://www.python.org/downloads/release/python-31210/"

echo ============================================
echo  PDF ChatBot - Windows install
echo  Target interpreter: Python %REQUIRED_VERSION% (amd64)
echo ============================================
echo.

rem --- Locate Python 3.12, preferring the py launcher's -3.12 selector ---
set "PYEXE="

where py >nul 2>&1
if %errorlevel%==0 (
    py -3.12 --version >nul 2>&1
    if !errorlevel!==0 (
        set "PYEXE=py -3.12"
    )
)

if "!PYEXE!"=="" (
    where python >nul 2>&1
    if !errorlevel!==0 (
        set "PYEXE=python"
    )
)

if "!PYEXE!"=="" (
    echo ERROR: No Python installation found on PATH.
    echo Install Python %REQUIRED_VERSION% ^(64-bit/amd64^) from:
    echo   %PYTHON_URL%
    echo Then re-run this script.
    exit /b 1
)

for /f "tokens=2" %%v in ('!PYEXE! --version 2^>^&1') do set "FOUND_VERSION=%%v"

echo Found Python !FOUND_VERSION! ^(via: !PYEXE!^)

if not "!FOUND_VERSION!"=="%REQUIRED_VERSION%" (
    echo.
    echo WARNING: Expected Python %REQUIRED_VERSION%, found !FOUND_VERSION!.
    echo Continuing anyway - if setup fails below, install %REQUIRED_VERSION% ^(amd64^) from:
    echo   %PYTHON_URL%
    echo.
)

rem --- Also confirm it's the 64-bit (amd64) build ---
!PYEXE! -c "import struct,sys; sys.exit(0 if struct.calcsize('P')*8==64 else 1)"
if not %errorlevel%==0 (
    echo ERROR: Found Python is not 64-bit ^(amd64^). Install the amd64 build:
    echo   %PYTHON_URL%
    exit /b 1
)

echo.
echo --- Creating virtual environment (venv\) ---
if exist venv (
    echo venv\ already exists, skipping creation.
) else (
    !PYEXE! -m venv venv
    if not !errorlevel!==0 (
        echo ERROR: Failed to create virtual environment.
        exit /b 1
    )
)

echo.
echo --- Installing dependencies ---
call venv\Scripts\python.exe -m pip install --upgrade pip
call venv\Scripts\pip.exe install -r requirements.txt
if not %errorlevel%==0 (
    echo ERROR: pip install failed.
    exit /b 1
)

echo.
echo --- Setting up .env ---
if exist .env (
    echo .env already exists, leaving it as-is.
) else (
    copy /y .env.example .env >nul
    echo Created .env from .env.example.
)

echo.
echo --- Running database migrations ---
call venv\Scripts\python.exe manage.py migrate
if not %errorlevel%==0 (
    echo ERROR: manage.py migrate failed.
    exit /b 1
)

echo.
echo ============================================
echo  Install complete.
echo  Next: venv\Scripts\python.exe manage.py runserver
echo  Then open http://127.0.0.1:8000/
echo ============================================

endlocal
