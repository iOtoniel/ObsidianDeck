@echo off
title Empacotar Obsidian Deck (.exe) com PyInstaller
cd /d "%~dp0"
echo ============================================================
echo   Gerando executavel ObsidianDeck.exe via PyInstaller...
echo ============================================================
py -m PyInstaller --noconfirm --onedir --windowed --name "ObsidianDeck" --collect-all customtkinter main.py
echo.
echo Concluido! O executavel foi gerado em: dist\ObsidianDeck\ObsidianDeck.exe
echo Copiando atalho para a pasta raiz do servidor...
if exist "dist\ObsidianDeck\ObsidianDeck.exe" (
    echo [OK] Executavel compilado com sucesso em dist\ObsidianDeck\ObsidianDeck.exe
)
pause
