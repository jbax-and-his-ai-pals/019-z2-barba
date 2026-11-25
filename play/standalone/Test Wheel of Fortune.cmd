@echo off
python "%~dp0..\..\tools\create_subgame_pack.py" --game wheel
if errorlevel 1 pause
