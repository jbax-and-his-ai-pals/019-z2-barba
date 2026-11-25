@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\tools\launch_subgame.ps1" -Game smb
if errorlevel 1 pause
