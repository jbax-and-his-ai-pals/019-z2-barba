@echo off
python "%~dp0..\..\..\tools\create_subgame_pack.py" --game duck --mmc3
if errorlevel 1 pause
