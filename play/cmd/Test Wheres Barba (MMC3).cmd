@echo off
python "%~dp0..\..\tools\create_waldo_pack.py" --mmc3
if errorlevel 1 pause
