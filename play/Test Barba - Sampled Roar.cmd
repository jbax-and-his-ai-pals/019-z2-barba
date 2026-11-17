@echo off
powershell.exe -NoProfile -File "%~dp0..\tools\launch_roar.ps1"
if errorlevel 1 pause
