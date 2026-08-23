@echo off
cd /d "%~dp0"
title Doc Classifier - Web UI
echo ==============================================
echo   Doc Classifier v0.1.0 - Web UI
echo ==============================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at venv\Scripts\python.exe
    echo Please create it first, then try again.
    pause
    exit /b 1
)

echo Starting web UI... Browser will open automatically.
echo Close this window to stop the web UI.
echo.
"venv\Scripts\python.exe" -m streamlit run "%~dp0src\doc_classifier\web.py"
pause