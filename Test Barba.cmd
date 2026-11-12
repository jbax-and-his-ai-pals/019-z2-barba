@echo off
powershell.exe -NoProfile -File "%~dp0tools\launch.ps1" -TestPack
if errorlevel 1 pause
