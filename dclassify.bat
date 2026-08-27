@echo off
cd /d "%~dp0"
title Doc Classifier - First Time Setup
echo ==============================================
echo   Doc Classifier v0.3.0 - First Time Setup
echo   (run this ONCE after download/extract)
echo ==============================================
echo.

REM --- 1. Check Python ---
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
    where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
    echo [ERROR] Python not found.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    echo Important: check "Add Python to PATH" during installation.
    echo Then run this file again.
    pause
    exit /b 1
)

%PYEXE% --version
echo [OK] Python detected.
echo.

REM --- 2. Create virtual environment if not exists ---
if exist "venv\Scripts\python.exe" (
    echo [OK] Virtual environment already exists, skipping.
) else (
    echo Creating virtual environment...
    %PYEXE% -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

REM --- 3. Upgrade pip then install app + dependencies ---
echo.
echo Upgrading pip...
"venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
echo Installing Doc Classifier and dependencies ^(2-5 min^)...
"venv\Scripts\python.exe" -m pip install -e . --quiet
if errorlevel 1 (
    echo [ERROR] Dependency installation failed. Check internet connection and try again.
    pause
    exit /b 1
)
echo [OK] Installation complete.
echo.

REM --- 4. Pre-pull default model if Ollama was just installed ---
set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if exist "%OLLAMA_EXE%" (
    echo.
    echo Pre-pulling default model qwen2.5:1.5b ^(±1 GB^)...
    "%OLLAMA_EXE%" pull qwen2.5:1.5b
    echo.
)

REM --- 5. Run guided setup (check Ollama / model / Tesseract) ---
echo Now checking AI readiness. Follow the on-screen prompts:
echo - If asked to install Ollama / download a model, just press Enter or Y.
echo - Progress is saved — you can close this window and resume later.
echo.
pause
call "venv\Scripts\dclassify.exe"

echo.
echo ==============================================
echo   Setup complete! From now on just double-click:
echo     - organize.bat      ^(auto-organize files^)
echo ==============================================
pause
