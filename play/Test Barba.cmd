@echo off
powershell.exe -NoProfile -File "%~dp0..\tools\launch.ps1" -TestPack
if errorlevel 1 pause
