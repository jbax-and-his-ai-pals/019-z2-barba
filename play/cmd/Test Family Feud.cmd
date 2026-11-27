@echo off
python "%~dp0..\..\tools\create_feud_pack.py"
if errorlevel 1 pause
