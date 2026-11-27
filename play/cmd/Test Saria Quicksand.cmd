@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\tools\launch.ps1" -TestPack -CheckpointSet saria
if errorlevel 1 pause
