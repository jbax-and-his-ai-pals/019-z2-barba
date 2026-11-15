@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\tools\launch.ps1" -TestPack -CheckpointSet world
if errorlevel 1 pause
