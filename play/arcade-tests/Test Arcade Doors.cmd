@echo off
python "%~dp0..\..\tools\create_portal_door_pack.py"
if errorlevel 1 pause
