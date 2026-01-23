@echo off
setlocal

cd /d "%~dp0"

REM init venv
call .venv\Scripts\activate.bat

REM run email job
python scripts\run_job.py

endlocal
pause
