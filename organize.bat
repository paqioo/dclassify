@echo off
cd /d "%~dp0"
title Doc Classifier - Auto Organizer
setlocal
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
echo ==============================================
echo   Doc Classifier v0.3.0 - Auto Organizer
echo   (opens interactive menu)
echo ==============================================
echo.

if not exist "venv\Scripts\dclassify.exe" (
    echo [ERROR] Application is not set up yet.
    echo Run dclassify.bat first, then try this file again.
    pause
    exit /b 1
)

echo Starting interactive menu...
echo.
call "venv\Scripts\dclassify.exe"
set "EXITCODE=%ERRORLEVEL%"

echo.
if "%EXITCODE%"=="0" (
    echo Done! Menu exited normally.
) else (
    echo Finished with issues - please check the output above.
)
endlocal
pause