@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\tools\launch.ps1" -TestPack -CheckpointSet movement
if errorlevel 1 pause
