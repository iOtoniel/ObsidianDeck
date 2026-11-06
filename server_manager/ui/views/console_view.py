"""
Console Integrado em Tempo Real:
- Logs coloridos por severidade (INFO, WARN, ERROR, PLAYER, CMD, SUCCESS)
- Filtro rápido de erros/avisos, busca textual e rolagem inteligente
- Envio de comandos com histórico navegável pelas setas (Cima / Baixo)
"""

from __future__ import annotations
from tkinter import filedialog
from typing import Callable, List, Tuple
import customtkinter as ctk

from ...config import ConfigManager
from ...process_manager import ServerProcessManager
from ...theme import PALETTE, font_body, font_heading, font_mono, font_small


class ConsoleView(ctk.CTkFrame):
    """Terminal interativo de baixa latência para o servidor Minecraft Vanilla."""

    TAG_COLORS = {
        "INFO": "#CBD5E1",
        "WARN": "#F59E0B",
        "ERROR": "#EF4444",
        "PLAYER": "#34D399",
        "SUCCESS": "#2ECC71",
        "CMD": "#38BDF8",
    }

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

        self.filter_mode = "ALL"
        self.search_query = ""
        self.history_idx = -1
        self.error_count = 0
        self.warn_count = 0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_terminal()
        self._build_command_bar()
        self.reload_full_log()

    def _build_toolbar(self) -> None:
        bar = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        bar.grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 8))
        bar.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            bar,
            text="Terminal do Servidor",
            font=font_heading(14, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=0, column=0, padx=(14, 12), pady=10, sticky="w")

        # Seletor de filtro
        self.seg_filter = ctk.CTkSegmentedButton(
            bar,
            values=["Todos os Logs", "Erros & Avisos", "Jogadores", "Comandos"],
            command=self._on_filter_change,
            font=font_small(11, bold=True),
            selected_color=PALETTE["lapis"],
            selected_hover_color=PALETTE["lapis_hover"],
            unselected_color=PALETTE["bg_elevated"],
        )
        self.seg_filter.set("Todos os Logs")
        self.seg_filter.grid(row=0, column=1, padx=6, pady=8, sticky="w")

        # Contadores de Erros e Avisos
        self.lbl_counters = ctk.CTkLabel(
            bar,
            text="0 Erros · 0 Avisos",
            font=font_mono(11, bold=True),
            text_color=PALETTE["text_secondary"],
        )
        self.lbl_counters.grid(row=0, column=2, padx=12, sticky="e")

        # Busca no console
        self.ent_search = ctk.CTkEntry(
            bar,
            placeholder_text="Filtrar texto no log...",
            width=180,
            height=28,
            font=font_small(11),
            fg_color=PALETTE["bg_console"],
            border_color=PALETTE["border_default"],
        )
        self.ent_search.grid(row=0, column=3, padx=6, pady=8)
        self.ent_search.bind("<KeyRelease>", self._on_search_change)

        self.var_autoscroll = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            bar,
            text="Auto-rolagem",
            variable=self.var_autoscroll,
            font=font_small(11),
            checkbox_width=16,
            checkbox_height=16,
            fg_color=PALETTE["emerald"],
            width=95,
        ).grid(row=0, column=4, padx=6)

        ctk.CTkButton(
            bar,
            text="Exportar",
            width=72,
            height=28,
            font=font_small(11),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["border_focus"],
            command=self._export_logs,
        ).grid(row=0, column=5, padx=4)

        ctk.CTkButton(
            bar,
            text="Limpar",
            width=64,
            height=28,
            font=font_small(11),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["redstone_dim"],
            command=self._clear_console,
        ).grid(row=0, column=6, padx=(4, 12))

    def _build_terminal(self) -> None:
        term_wrap = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_console"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        term_wrap.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 8))
        term_wrap.grid_columnconfigure(0, weight=1)
        term_wrap.grid_rowconfigure(0, weight=1)

        self.textbox = ctk.CTkTextbox(
            term_wrap,
            fg_color=PALETTE["bg_console"],
            text_color=PALETTE["text_primary"],
            font=font_mono(12),
            wrap="word",
            border_width=0,
            corner_radius=6,
        )
        self.textbox.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        # Configurar tags de cores no widget tk.Text subjacente
        tk_text = self.textbox._textbox
        for tag, color in self.TAG_COLORS.items():
            bg = "#281115" if tag == "ERROR" else ("#241B0E" if tag == "WARN" else "")
            if bg:
                tk_text.tag_config(tag, foreground=color, background=bg)
            else:
                tk_text.tag_config(tag, foreground=color)

        self.textbox.configure(state="disabled")

    def _build_command_bar(self) -> None:
        bottom = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        bottom.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 4))
        bottom.grid_columnconfigure(1, weight=1)

        # Pílulas de comandos rápidos
        pills_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        pills_frame.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(8, 4))

        ctk.CTkLabel(
            pills_frame,
            text="Atalhos:",
            font=font_small(11),
            text_color=PALETTE["text_muted"],
        ).pack(side="left", padx=(0, 6))

        presets = [
            ("list", "list"),
            ("save-all", "save-all"),
            ("help", "help"),
            ("whitelist list", "whitelist list"),
            ("time set day", "time set day"),
            ("weather clear", "weather clear"),
            ("gamerule keepInventory true", "gamerule keepInventory true"),
        ]
        for lbl, cmd in presets:
            ctk.CTkButton(
                pills_frame,
                text=lbl,
                height=24,
                width=len(lbl) * 7 + 16,
                font=font_mono(11),
                fg_color=PALETTE["bg_elevated"],
                hover_color=PALETTE["border_focus"],
                text_color=PALETTE["text_secondary"],
                corner_radius=4,
                command=lambda c=cmd: self._fill_or_send(c),
            ).pack(side="left", padx=3)

        # Prompt de entrada
        ctk.CTkLabel(
            bottom,
            text=">",
            font=font_mono(15, bold=True),
            text_color=PALETTE["emerald"],
        ).grid(row=1, column=0, padx=(14, 6), pady=(4, 10))

        self.ent_cmd = ctk.CTkEntry(
            bottom,
            placeholder_text="Digite um comando Vanilla (ex: say Olá, op iTonyTony, gamemode creative cintiasz)... [Setas ↑/↓ para histórico]",
            font=font_mono(12),
            height=34,
            fg_color=PALETTE["bg_console"],
            border_color=PALETTE["border_default"],
        )
        self.ent_cmd.grid(row=1, column=1, sticky="ew", padx=4, pady=(4, 10))
        self.ent_cmd.bind("<Return>", lambda _e: self._submit_command())
        self.ent_cmd.bind("<Up>", self._history_prev)
        self.ent_cmd.bind("<Down>", self._history_next)

        ctk.CTkButton(
            bottom,
            text="Enviar Comando",
            command=self._submit_command,
            font=font_body(12, bold=True),
            fg_color=PALETTE["emerald"],
            hover_color=PALETTE["emerald_hover"],
            text_color=PALETTE["text_inverse"],
            height=34,
            width=135,
            corner_radius=5,
        ).grid(row=1, column=2, padx=(6, 12), pady=(4, 10))

    def _matches_filter(self, line: str, level: str) -> bool:
        if self.filter_mode == "Erros & Avisos" and level not in ("ERROR", "WARN"):
            return False
        if self.filter_mode == "Jogadores" and level != "PLAYER":
            return False
        if self.filter_mode == "Comandos" and level != "CMD":
            return False
        if self.search_query and self.search_query.lower() not in line.lower():
            return False
        return True

    def append_log_lines(self, entries: List[Tuple[str, str]]) -> None:
        if not entries:
            return
        tk_text = self.textbox._textbox
        self.textbox.configure(state="normal")
        for line, level in entries:
            if level == "ERROR":
                self.error_count += 1
            elif level == "WARN":
                self.warn_count += 1
            if self._matches_filter(line, level):
                tag = level if level in self.TAG_COLORS else "INFO"
                tk_text.insert("end", line + "\n", tag)
        self.textbox.configure(state="disabled")
        self._update_counters_label()
        if self.var_autoscroll.get():
            self.textbox.see("end")

    def reload_full_log(self) -> None:
        self.error_count = 0
        self.warn_count = 0
        tk_text = self.textbox._textbox
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        for line, level in list(self.process_mgr.log_history):
            if level == "ERROR":
                self.error_count += 1
            elif level == "WARN":
                self.warn_count += 1
            if self._matches_filter(line, level):
                tag = level if level in self.TAG_COLORS else "INFO"
                tk_text.insert("end", line + "\n", tag)
        self.textbox.configure(state="disabled")
        self._update_counters_label()
        if self.var_autoscroll.get():
            self.textbox.see("end")

    def _update_counters_label(self) -> None:
        color = PALETTE["redstone"] if self.error_count > 0 else (PALETTE["copper"] if self.warn_count > 0 else PALETTE["text_secondary"])
        self.lbl_counters.configure(
            text=f"{self.error_count} Erros · {self.warn_count} Avisos",
            text_color=color,
        )

    def _on_filter_change(self, val: str) -> None:
        self.filter_mode = val
        self.reload_full_log()

    def _on_search_change(self, _event=None) -> None:
        self.search_query = self.ent_search.get().strip()
        self.reload_full_log()

    def _fill_or_send(self, cmd: str) -> None:
        if self.process_mgr.is_running():
            self.process_mgr.send_command(cmd)
        else:
            self.ent_cmd.delete(0, "end")
            self.ent_cmd.insert(0, cmd)
            self.ent_cmd.focus_set()

    def _submit_command(self) -> None:
        cmd = self.ent_cmd.get().strip()
        if not cmd:
            return
        self.ent_cmd.delete(0, "end")
        self.history_idx = -1
        if not self.process_mgr.is_running():
            self.notify_cb("O servidor está offline. Inicie-o para executar comandos.", "warning")
            return
        self.process_mgr.send_command(cmd)

    def _history_prev(self, _event=None) -> str:
        hist: List[str] = self.config.get("command_history", [])
        if not hist:
            return "break"
        self.history_idx = min(len(hist) - 1, self.history_idx + 1)
        self.ent_cmd.delete(0, "end")
        self.ent_cmd.insert(0, hist[self.history_idx])
        return "break"

    def _history_next(self, _event=None) -> str:
        hist: List[str] = self.config.get("command_history", [])
        if not hist:
            return "break"
        if self.history_idx > 0:
            self.history_idx -= 1
            self.ent_cmd.delete(0, "end")
            self.ent_cmd.insert(0, hist[self.history_idx])
        else:
            self.history_idx = -1
            self.ent_cmd.delete(0, "end")
        return "break"

    def _clear_console(self) -> None:
        self.process_mgr.log_history.clear()
        self.reload_full_log()
        self.notify_cb("Visualização do console limpa.", "info")

    def _export_logs(self) -> None:
        target = filedialog.asksaveasfilename(
            title="Exportar Log do Console",
            defaultextension=".log",
            initialfile="servidor_console_export.log",
            filetypes=[("Arquivo de Log", "*.log"), ("Texto", "*.txt")],
        )
        if not target:
            return
        try:
            text_out = "\n".join(line for line, _lvl in self.process_mgr.log_history)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text_out + "\n")
            self.notify_cb(f"Log exportado com sucesso para {target}", "success")
        except Exception as exc:
            self.notify_cb(f"Erro ao exportar log: {exc}", "error")
