@echo off
:: install-octop.bat — Portable Octop installer (no pip, uses uv)
:: Usage: Run as Administrator (only for adding to PATH).
::   - Installs uv if not present
::   - Creates a venv in %USERPROFILE%\.octop\venv
::   - Installs octop wheel
::   - Optionally creates desktop shortcut
::
:: Options (pass as env or on command line):
::   SET OCTOP_HOME=dir      — Override OCTOP_HOME (default: %USERPROFILE%\.octop)
::   SET PYTHON=path        — Python executable to use (default: python from PATH)
::   SET NO_SHORTCUT=1      — Skip desktop shortcut creation
::   SET PORTABLE=1         — Bundle a portable Python (recommended for distribution)

setlocal enabledelayedexpansion

set "OCTOP_HOME=%USERPROFILE%\.octop"
set "PORTABLE_PYTHON_URL=https://github.com/indygreg/python-build-standalone/releases/download/20250113/cpython-3.13.1%2B20250113-x86_64-pc-windows-msvc-share.zip"

:: ── Parse args ───────────────────────────────────────────────────────────────
for %%A in (%*) do (
    if /i "%%A"=="--help" goto :help
    if /i "%%A"=="-h" goto :help
    if /i "%%A"=="--portable" set "FORCE_PORTABLE=1"
    if /i "%%A"=="--no-shortcut" set "NO_SHORTCUT=1"
    if /i "%%A"=="--home" (
        set "NEXT_ARG=1"
    ) else if defined NEXT_ARG (
        set "OCTOP_HOME=%%A"
        set "NEXT_ARG="
    )
)

goto :main

:help
echo install-octop.bat  —  Install Octop backend (portable, no admin required)
echo.
echo Usage: install-octop.bat [OPTIONS]
echo.
echo Options:
echo   --portable     Download and bundle a portable Python 3.13 (recommended)
echo   --no-shortcut  Skip creating a Start Menu shortcut
echo   --home DIR     Set OCTOP_HOME directory (default: %%USERPROFILE%%\.octop)
echo   --help         Show this help message
echo.
echo Environment:
echo   PORTABLE_PYTHON_URL  Override portable Python zip URL
echo   OCTOP_HOME           Override install directory
exit /b 0

:main
echo[========================================================
echo  Octop Backend Installer  (熊宝 Agent)
echo  Install dir: %OCTOP_HOME%%
echo[========================================================

:: ── 1. Bootstrap uv ──────────────────────────────────────────────────────────
where uv >nul 2>&1
if errorlevel 1 (
    echo [1/5] Installing uv ...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 ^| iex"
    if errorlevel 1 (
        echo ERROR: Failed to install uv. Please install from https://astral.sh/uv
        exit /b 1
    )
    :: Refresh PATH so uv is available in this session
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
) else (
    echo [1/5] uv found: ok
)

:: ── 2. Python bootstrap ─────────────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 goto :no_python

:: Check if --portable or no system Python 3.12+
python --version 2>nul | findstr /C:"Python 3.1" >nul
if errorlevel 1 (
    if defined FORCE_PORTABLE goto :install_portable
    echo [WARNING] Python found but not 3.12+. Use --portable for bundled Python 3.13.
)

:python_ok
echo [2/5] Python: ok

:: ── 3. Create venv ─────────────────────────────────────────────────────────
echo [3/5] Creating venv ...
if not exist "%OCTOP_HOME%" mkdir "%OCTOP_HOME%"
if not exist "%OCTOP_HOME%\venv" (
    uv venv --python 3.12 "%OCTOP_HOME%\venv"
) else (
    echo      venv already exists, skipping
)

:: ── 4. Install wheel ────────────────────────────────────────────────────────
echo [4/5] Installing octop wheel ...
:: Find the wheel in the same folder as this script, or ./dist
set "WHEEL_DIR=%~dp0"
if not exist "%WHEEL_DIR%dist" set "WHEEL_DIR=%~dp0..\octop\"

for /f "delims=" %%F in ('dir /b /o-n "%WHEEL_DIR%dist\octop-*-py3-none-any.whl" 2^>nul') do (
    set "WHEEL_FILE=%WHEEL_DIR%dist\%%F"
    goto :found_wheel
)
:found_wheel
if not defined WHEEL_FILE (
    echo ERROR: Could not find octop-*-py3-none-any.whl in %WHEEL_DIR%dist
    echo Please place the wheel file or run this script from the unpacked archive root.
    exit /b 1
)
echo      Installing !WHEEL_FILE!
"%OCTOP_HOME%\venv\Scripts\pip.exe" install "!WHEEL_FILE!"
if errorlevel 1 (
    echo ERROR: pip install failed
    exit /b 1
)

:: ── 5. Post-install ─────────────────────────────────────────────────────────
echo [5/5] Post-install ...
:: Create logs directory
if not exist "%OCTOP_HOME%\logs" mkdir "%OCTOP_HOME%\logs"

:: Test run
echo      Testing octop CLI ...
"%OCTOP_HOME%\venv\Scripts\octop.exe" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: octop CLI failed. Check %OCTOP_HOME%\logs\octop.err.log
    exit /b 1
)

:: ── Optional: Start Menu shortcut ────────────────────────────────────────────
if not defined NO_SHORTCUT (
    powershell -ExecutionPolicy Bypass -Command "
        $ws = New-Object -ComObject WScript.Shell
        $sc = $ws.CreateShortcut('%USERPROFILE%\Start Menu\Programs\熊宝Agent后端.lnk')
        $sc.TargetPath = '%OCTOP_HOME%\venv\Scripts\octop.exe'
        $sc.Arguments = 'run'
        $sc.WorkingDirectory = '%OCTOP_HOME%'
        $sc.Description = '熊宝 Agent — Octop 后端服务'
        $sc.Save()
        Write-Host 'Created Start Menu shortcut'
    "
)

echo[
echo  ✓ Installation complete!
echo[
echo  Next steps:
echo    1. Run: octop run
echo       (from %OCTOP_HOME%\venv\Scripts\octop.exe)
echo       Or double-click the Start Menu shortcut.
echo    2. Open: http://127.0.0.1:8088
echo[
exit /b 0

:: ── Portable Python bootstrap ────────────────────────────────────────────────
:install_portable
echo [2/5] Downloading portable Python 3.13 ...
set "PYTHON_ZIP=%TEMP%\cpython-portable.zip"
set "PYTHON_DIR=%OCTOP_HOME%\python"

if exist "%PYTHON_DIR%\python.exe" (
    echo      Portable Python already present, skipping download
) else (
    powershell -ExecutionPolicy Bypass -Command "
        $ProgressPreference = 'SilentlyContinue'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Write-Host 'Downloading portable Python (~25 MB)...'
        Invoke-WebRequest -Uri '%PORTABLE_PYTHON_URL%' -OutFile '%PYTHON_ZIP%' -UseBasicParsing
        Write-Host 'Extracting...'
        if (Test-Path '%PYTHON_DIR%') { Remove-Item '%PYTHON_DIR%' -Recurse -Force }
        Expand-Archive -Path '%PYTHON_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force
        Remove-Item '%PYTHON_ZIP%'
        Write-Host 'Portable Python extracted'
    "
    if errorlevel 1 (
        echo ERROR: Failed to download portable Python
        exit /b 1
    )
)
set "PYTHON=%PYTHON_DIR%\python.exe"
goto :python_ok

:no_python
echo ERROR: Python not found in PATH.
echo Use --portable to download a bundled Python, or install Python 3.12+ from python.org
exit /b 1
