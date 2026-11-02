@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul || (echo [!] Python is not installed. Install it from python.org first. & pause & exit /b)
py -m pip install --quiet --disable-pip-version-check numpy pillow
start "" pyw kakao_nag.py
