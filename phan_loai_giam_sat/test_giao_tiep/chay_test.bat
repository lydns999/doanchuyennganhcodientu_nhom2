@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py
start "" http://localhost:8000
%PY% server_don_gian.py
pause
