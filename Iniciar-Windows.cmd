@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto python
py -3 laboratorio.py --abrir
goto fim
:python
python laboratorio.py --abrir
:fim
pause
