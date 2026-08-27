@echo off
cd /d "%~dp0"
title Doc Classifier - Setup Awal
echo ==============================================
echo   Doc Classifier v0.3.0 - Setup Awal
echo   (jalankan ini SEKALI setelah download/extract)
echo ==============================================
echo.

REM --- 1. Cek Python ---
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
    where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
    echo [ERROR] Python tidak ditemukan.
    echo Silakan install Python 3.10+ dari https://www.python.org/downloads/
    echo Penting: centang "Add Python to PATH" saat instalasi.
    echo Setelah itu, jalankan lagi file ini.
    pause
    exit /b 1
)

%PYEXE% --version
echo [OK] Python terdeteksi.
echo.

REM --- 2. Buat virtual environment jika belum ada ---
if exist "venv\Scripts\python.exe" (
    echo [OK] Virtual environment sudah ada, lewati pembuatan.
) else (
    echo Membuat virtual environment...
    %PYEXE% -m venv venv
    if errorlevel 1 (
        echo [ERROR] Gagal membuat virtual environment.
        pause
        exit /b 1
    )
)

REM --- 3. Upgrade pip lalu install aplikasi + dependensi ---
echo.
echo Meng-upgrade pip...
"venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
echo Meng-install Doc Classifier beserta dependensi ^(2-5 menit^)...
"venv\Scripts\python.exe" -m pip install -e . --quiet
if errorlevel 1 (
    echo [ERROR] Instalasi dependensi gagal. Periksa koneksi internet lalu ulangi.
    pause
    exit /b 1
)
echo [OK] Instalasi selesai.
echo.

REM --- 4. Jalankan setup terpandu (cek Ollama / model / Tesseract) ---
echo Sekarang kita cek persiapan AI. Ikuti petunjuk di layar:
echo - Jika diminta install Ollama / download model, cukup tekan Enter atau Y.
echo - Progres tidak hilang walau Anda tutup jendela ini.
echo.
pause
call "venv\Scripts\dclassify.exe"

echo.
echo ==============================================
echo   Setup selesai! Ke depan cukup klik dua kali:
echo     - Rapikan_Downloads.bat  ^(perapikan otomatis^)
echo     - Jalankan_Web_UI.bat    ^(buka Web UI^)
echo ==============================================
pause
