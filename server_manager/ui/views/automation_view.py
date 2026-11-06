"""
Painel de Automação, Recuperação de Falhas (Watchdog) e Inicialização Automática.
"""

from __future__ import annotations
import os
from pathlib import Path
import sys
from typing import Callable
import customtkinter as ctk

from ...config import ConfigManager
from ...process_manager import ServerProcessManager
from ...theme import PALETTE, font_body, font_heading, font_mono, font_small


class AutomationView(ctk.CTkScrollableFrame):
    """Configurações de inicialização automática, auto-restart em falhas e reinício diário."""

    STARTUP_SCRIPT_NAME = "ObsidianDeck_MinecraftManager_Autostart.cmd"

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        config: ConfigManager,
        process_mgr: ServerProcessManager,
        notify_cb: Callable[[str, str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.config = config
        self.process_mgr = process_mgr
        self.notify_cb = notify_cb

        self.grid_columnconfigure(0, weight=1)

        self._build_startup_card()
        self._build_watchdog_card()
        self._build_scheduled_restart_card()
        self._build_eula_and_safety_card()

    @staticmethod
    def _get_windows_startup_file() -> Path:
        appdata = os.environ.get("APPDATA", "")
        startup_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        return startup_dir / AutomationView.STARTUP_SCRIPT_NAME

    def _is_windows_autostart_enabled(self) -> bool:
        return self._get_windows_startup_file().exists()

    def _toggle_windows_autostart(self) -> None:
        target = self._get_windows_startup_file()
        if self.var_win_startup.get():
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                if getattr(sys, "frozen", False):
                    cmd_line = f'start "" "{sys.executable}"'
                else:
                    main_py = self.config.base_dir / "main.py"
                    cmd_line = f'start "" "{sys.executable}" "{main_py}"'
                content = f"@echo off\ncd /d \"{self.config.base_dir}\"\n{cmd_line}\n"
                target.write_text(content, encoding="utf-8")
                self.notify_cb("Inicialização com o Windows ativada na pasta Startup do usuário.", "success")
            except Exception as exc:
                self.var_win_startup.set(False)
                self.notify_cb(f"Não foi possível configurar inicialização do Windows: {exc}", "error")
        else:
            try:
                target.unlink(missing_ok=True)
                self.notify_cb("Inicialização automática com o Windows desativada.", "info")
            except Exception as exc:
                self.notify_cb(f"Erro ao remover atalho de inicialização: {exc}", "error")

    def _build_startup_card(self) -> None:
        card = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        card.grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 10))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Inicialização Automática",
            font=font_heading(14, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        ctk.CTkLabel(
            card,
            text="Configure o comportamento ao abrir o gerenciador ou iniciar o Windows.",
            font=font_small(11),
            text_color=PALETTE["text_secondary"],
        ).grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        self.var_auto_launch = ctk.BooleanVar(value=bool(self.config.get("auto_start_server_on_launch", False)))
        ctk.CTkSwitch(
            card,
            text="Iniciar o servidor Minecraft automaticamente ao abrir o Obsidian Deck",
            variable=self.var_auto_launch,
            command=self._save_automation,
            font=font_body(12, bold=True),
            progress_color=PALETTE["emerald"],
        ).grid(row=2, column=0, padx=16, pady=(2, 10), sticky="w")

        self.var_win_startup = ctk.BooleanVar(value=self._is_windows_autostart_enabled())
        ctk.CTkSwitch(
            card,
            text="Iniciar o gerenciador Obsidian Deck automaticamente ao fazer login no Windows",
            variable=self.var_win_startup,
            command=self._toggle_windows_autostart,
            font=font_body(12, bold=True),
            progress_color=PALETTE["lapis"],
        ).grid(row=3, column=0, padx=16, pady=(0, 14), sticky="w")

    def _build_watchdog_card(self) -> None:
        card = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        card.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Detecção de Falhas (Watchdog) & Auto-Reinicialização",
            font=font_heading(14, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        ctk.CTkLabel(
            card,
            text="Monitora continuamente o processo Java. Se o servidor encerrar com código de erro (crash), reinicia sozinho.",
            font=font_small(11),
            text_color=PALETTE["text_secondary"],
        ).grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        self.var_crash_restart = ctk.BooleanVar(value=bool(self.config.get("auto_restart_on_crash", True)))
        ctk.CTkSwitch(
            card,
            text="Reiniciar servidor automaticamente quando uma queda inesperada for detectada",
            variable=self.var_crash_restart,
            command=self._save_automation,
            font=font_body(12, bold=True),
            progress_color=PALETTE["copper"],
        ).grid(row=2, column=0, padx=16, pady=(2, 10), sticky="w")

        opts_row = ctk.CTkFrame(card, fg_color="transparent")
        opts_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 14))

        ctk.CTkLabel(
            opts_row,
            text="Máximo de tentativas consecutivas:",
            font=font_small(12),
            text_color=PALETTE["text_secondary"],
        ).pack(side="left", padx=(0, 8))

        self.cmb_max_retries = ctk.CTkOptionMenu(
            opts_row,
            values=["1", "2", "3", "5", "10"],
            width=80,
            height=28,
            font=font_mono(12),
            fg_color=PALETTE["bg_elevated"],
            button_color=PALETTE["copper"],
            command=lambda _v: self._save_automation(),
        )
        self.cmb_max_retries.set(str(self.config.get("max_crash_restarts", 3)))
        self.cmb_max_retries.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(
            opts_row,
            text="Intervalo de espera antes de religar (segundos):",
            font=font_small(12),
            text_color=PALETTE["text_secondary"],
        ).pack(side="left", padx=(0, 8))

        self.cmb_delay = ctk.CTkOptionMenu(
            opts_row,
            values=["5", "10", "15", "30", "60"],
            width=80,
            height=28,
            font=font_mono(12),
            fg_color=PALETTE["bg_elevated"],
            button_color=PALETTE["copper"],
            command=lambda _v: self._save_automation(),
        )
        self.cmb_delay.set(str(self.config.get("crash_restart_delay_sec", 10)))
        self.cmb_delay.pack(side="left")

    def _build_scheduled_restart_card(self) -> None:
        card = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        card.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Reinicialização Programada Diária",
            font=font_heading(14, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        ctk.CTkLabel(
            card,
            text="Envia avisos automáticos no chat aos jogadores e reinicia o servidor no horário escolhido para liberar memória.",
            font=font_small(11),
            text_color=PALETTE["text_secondary"],
        ).grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))

        self.var_sched_restart = ctk.BooleanVar(value=bool(self.config.get("scheduled_restart_enabled", False)))
        ctk.CTkSwitch(
            row,
            text="Ativar Reinício Diário no Horário (HH:MM):",
            variable=self.var_sched_restart,
            command=self._save_automation,
            font=font_body(12, bold=True),
            progress_color=PALETTE["amethyst"],
        ).pack(side="left", padx=(0, 12))

        self.ent_restart_time = ctk.CTkEntry(
            row,
            width=90,
            height=28,
            font=font_mono(12, bold=True),
            fg_color=PALETTE["bg_console"],
            border_color=PALETTE["border_default"],
        )
        self.ent_restart_time.insert(0, str(self.config.get("scheduled_restart_time", "04:00")))
        self.ent_restart_time.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            row,
            text="Aplicar Horário",
            width=115,
            height=28,
            font=font_small(11, bold=True),
            fg_color=PALETTE["lapis"],
            hover_color=PALETTE["lapis_hover"],
            command=self._save_automation,
        ).pack(side="left")

    def _build_eula_and_safety_card(self) -> None:
        card = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        card.grid(row=3, column=0, sticky="ew", padx=4, pady=(0, 10))
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text="Segurança de Dados & Licença EULA",
            font=font_heading(14, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=0, column=0, padx=16, pady=(14, 8), sticky="w")

        self.var_safe_exit = ctk.BooleanVar(value=bool(self.config.get("safe_stop_on_exit", True)))
        ctk.CTkSwitch(
            card,
            text="Ao fechar o gerenciador, salvar mundos (save-all) e parar o servidor com segurança",
            variable=self.var_safe_exit,
            command=self._save_automation,
            font=font_body(12, bold=True),
            progress_color=PALETTE["emerald"],
        ).grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        eula_row = ctk.CTkFrame(card, fg_color="transparent")
        eula_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 14))

        eula_ok = self.process_mgr.check_eula_accepted()
        self.lbl_eula = ctk.CTkLabel(
            eula_row,
            text=f"Status do arquivo eula.txt: {'ACEITO (eula=true)' if eula_ok else 'PENDENTE (eula=false)'}",
            font=font_mono(12, bold=True),
            text_color=PALETTE["emerald"] if eula_ok else PALETTE["copper"],
        )
        self.lbl_eula.pack(side="left", padx=(0, 14))

        ctk.CTkButton(
            eula_row,
            text="Confirmar eula=true",
            width=145,
            height=28,
            font=font_small(11, bold=True),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["emerald"],
            command=self._accept_eula_btn,
        ).pack(side="left")

    def _accept_eula_btn(self) -> None:
        if self.process_mgr.accept_eula():
            self.lbl_eula.configure(text="Status do arquivo eula.txt: ACEITO (eula=true)", text_color=PALETTE["emerald"])
            self.notify_cb("Arquivo eula.txt atualizado com eula=true.", "success")

    def _save_automation(self) -> None:
        t_str = self.ent_restart_time.get().strip()
        if len(t_str) != 5 or ":" not in t_str:
            t_str = "04:00"
        self.config.set("auto_start_server_on_launch", bool(self.var_auto_launch.get()), auto_save=False)
        self.config.set("auto_restart_on_crash", bool(self.var_crash_restart.get()), auto_save=False)
        self.config.set("max_crash_restarts", int(self.cmb_max_retries.get()), auto_save=False)
        self.config.set("crash_restart_delay_sec", int(self.cmb_delay.get()), auto_save=False)
        self.config.set("scheduled_restart_enabled", bool(self.var_sched_restart.get()), auto_save=False)
        self.config.set("scheduled_restart_time", t_str, auto_save=False)
        self.config.set("safe_stop_on_exit", bool(self.var_safe_exit.get()), auto_save=True)
        self.notify_cb("Preferências de automação e segurança salvas.", "success")
