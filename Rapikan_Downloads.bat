@echo off
cd /d "%~dp0"
title Doc Classifier - Auto Organize
setlocal
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
echo ==============================================
echo   Doc Classifier v0.1.0 - File Type Organizer
echo   (interactive menu mode)
echo ==============================================
echo.

if not exist "venv\Scripts\dclassify.exe" (
    echo [ERROR] Aplikasi belum ter-setup.
    echo Jalankan Setup_Awal.bat terlebih dahulu, lalu ulangi file ini.
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