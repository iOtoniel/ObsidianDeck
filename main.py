"""
Ponto de entrada do Obsidian Deck — Minecraft Vanilla Server Manager.
Execute com: `py main.py` ou pelo atalho `iniciar_painel.bat`.
"""

from __future__ import annotations
import ctypes
import sys
from tkinter import messagebox

from server_manager.ui.app import MinecraftServerManagerApp


def enable_windows_dpi_awareness() -> None:
    """Ativa nitidez High-DPI em monitores Windows 10/11."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def main() -> None:
    enable_windows_dpi_awareness()
    try:
        app = MinecraftServerManagerApp()
        app.mainloop()
    except Exception as exc:
        messagebox.showerror("Erro Fatal ao Iniciar Painel", f"Ocorreu um erro inesperado:\n{exc}")
        raise


if __name__ == "__main__":
    main()
