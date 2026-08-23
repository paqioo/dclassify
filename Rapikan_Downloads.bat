@echo off
cd /d "%~dp0"
title Doc Classifier - Auto Organize
setlocal
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
echo ==============================================
echo   Doc Classifier v0.1.0 - Auto Organize
echo ==============================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found at venv\Scripts\python.exe
    echo Please create it first, then try again.
    pause
    exit /b 1
)

echo [1/2] Checking AI connection (Ollama)...
echo.
"venv\Scripts\python.exe" -m doc_classifier.cli check
if errorlevel 1 (
    echo.
    echo [IMPORTANT] AI connection check FAILED.
    echo Please start Ollama first, then run this file again.
    pause
    exit /b 1
)
echo.

echo [2/2] Classifying and organizing documents from source folder...
echo.
"venv\Scripts\python.exe" -m doc_classifier.cli classify
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
    echo Done! Documents have been organized.
) else (
    echo Finished with issues - please check the output above.
)
endlocal
pause