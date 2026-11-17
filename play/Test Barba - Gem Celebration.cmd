@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\tools\launch.ps1" -TestPack -CheckpointSet gem
if errorlevel 1 pause
