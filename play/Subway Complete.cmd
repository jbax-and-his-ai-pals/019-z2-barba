@echo off
python "%~dp0..\tools\subway_complete.py"
if errorlevel 1 pause
