@echo off
python "%~dp0..\..\tools\create_subgame_pack.py" --game mtpo
if errorlevel 1 pause
