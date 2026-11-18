@echo off
python "%~dp0..\tools\create_waldo_pack.py"
if errorlevel 1 pause
