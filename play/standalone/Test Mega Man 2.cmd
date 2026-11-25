@echo off
python "%~dp0..\..\tools\create_subgame_pack.py" --game mm2
if errorlevel 1 pause
