@echo off
title Obsidian Deck - Minecraft Server Manager
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    start "" pyw main.py
) else (
    start "" pythonw main.py
)
