@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0..\.."
if not exist "src\__main__.py" (
    echo Error: src\__main__.py not found. Run from repo root.
    pause
    exit /b 1
)

set "PY=python"
if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo Repo root: %CD%
echo Using: %PY%
echo Running PyInstaller...
"%PY%" -m PyInstaller "build\Windows-template\Tkonverter.spec"
if errorlevel 1 (
    echo PyInstaller failed.
    pause
    exit /b 1
)

echo Done. Exe: dist\Tkonverter\Tkonverter.exe
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
    set /p yn="Build Inno Setup installer? (y/n): "
    if /i "!yn!"=="y" (
        "%ISCC%" "%~dp0inno_setup_6.iss"
        if not errorlevel 1 echo Installer: build\Windows-template\Output\Tkonverter_Setup_v1.0.0.exe
    )
) else (
    echo Inno Setup 6 not found. Installer skipped.
)
pause
