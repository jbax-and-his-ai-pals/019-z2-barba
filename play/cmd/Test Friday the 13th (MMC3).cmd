@echo off
python "%~dp0..\..\tools\create_f13_pack.py" --mmc3
if errorlevel 1 pause
