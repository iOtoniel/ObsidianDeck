"""
Painel de Backups do Mundo:
- Criação manual em segundo plano com barra de progresso
- Restauração segura com confirmação e backup prévio automático
- Agendamento periódico e política de retenção
"""

from __future__ import annotations
import os
from pathlib import Path
from tkinter import messagebox
from typing import Callable
import customtkinter as ctk

from ...backup_manager import BackupManager
from ...config import ConfigManager
from ...process_manager import ServerProcessManager
from ...theme import PALETTE, font_body, font_heading, font_mono, font_small


class BackupsView(ctk.CTkScrollableFrame):
    """Gerenciamento de snapshots compactados (.zip) do mundo e agendamento automático."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        config: ConfigManager,
        backup_mgr: BackupManager,
        process_mgr: ServerProcessManager,
        notify_cb: Callable[[str, str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.config = config
        self.backup_mgr = backup_mgr
        self.process_mgr = process_mgr
        self.notify_cb = notify_cb

        self.grid_columnconfigure(0, weight=1)

        self._build_create_panel()
        self._build_schedule_panel()
        self._build_backups_list()
        self.refresh_backups()

    def _build_create_panel(self) -> None:
        panel = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        panel.grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 8))
        panel.grid_columnconfigure(1, weight=1)

        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.grid(row=0, column=0, columnspan=4, sticky="ew", padx=16, pady=(12, 4))
        hdr.grid_columnconfigure(0, weight=1)

        self.lbl_world_info = ctk.CTkLabel(
            hdr,
            text="Mundo Ativo: world",
            font=font_heading(14, bold=True),
            text_color=PALETTE["text_primary"],
        )
        self.lbl_world_info.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            hdr,
            text="Abrir Pasta de Backups",
            width=155,
            height=28,
            font=font_small(11),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["border_focus"],
            command=self._open_backup_folder,
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            panel,
            text="Identificador (Tag):",
            font=font_body(12),
            text_color=PALETTE["text_secondary"],
        ).grid(row=1, column=0, padx=(16, 8), pady=10, sticky="w")

        self.ent_tag = ctk.CTkEntry(
            panel,
            placeholder_text="Ex: antes-nether, castelo-pronto, manual...",
            height=32,
            font=font_mono(12),
            fg_color=PALETTE["bg_console"],
            border_color=PALETTE["border_default"],
        )
        self.ent_tag.insert(0, "manual")
        self.ent_tag.grid(row=1, column=1, sticky="ew", padx=6, pady=10)

        self.btn_create = ctk.CTkButton(
            panel,
            text="Criar Backup Agora",
            command=self._start_manual_backup,
            font=font_body(12, bold=True),
            fg_color=PALETTE["emerald"],
            hover_color=PALETTE["emerald_hover"],
            text_color=PALETTE["text_inverse"],
            height=32,
            width=165,
            corner_radius=5,
        )
        self.btn_create.grid(row=1, column=2, padx=(6, 16), pady=10)

        # Barra de progresso e status
        prog_row = ctk.CTkFrame(panel, fg_color="transparent")
        prog_row.grid(row=2, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 12))
        prog_row.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(
            prog_row,
            height=8,
            progress_color=PALETTE["emerald"],
            fg_color=PALETTE["bg_console"],
        )
        self.progress.set(0.0)
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 12))

        self.lbl_prog_status = ctk.CTkLabel(
            prog_row,
            text="Pronto para criar backup seguro (sincroniza chunks automaticamente se online).",
            font=font_small(11),
            text_color=PALETTE["text_muted"],
        )
        self.lbl_prog_status.grid(row=1, column=0, sticky="w", pady=(4, 0))

    def _build_schedule_panel(self) -> None:
        panel = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        panel.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 10))
        panel.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(
            panel,
            text="Agendamento Automático de Backups",
            font=font_heading(13, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=0, column=0, columnspan=6, padx=16, pady=(12, 6), sticky="w")

        self.var_auto_enabled = ctk.BooleanVar(value=bool(self.config.get("auto_backup_enabled", False)))
        ctk.CTkSwitch(
            panel,
            text="Ativar Backups Periódicos",
            variable=self.var_auto_enabled,
            font=font_body(12, bold=True),
            progress_color=PALETTE["emerald"],
        ).grid(row=1, column=0, padx=(16, 14), pady=(4, 14), sticky="w")

        ctk.CTkLabel(panel, text="Intervalo (min):", font=font_small(12), text_color=PALETTE["text_secondary"]).grid(
            row=1, column=1, padx=(6, 4), pady=(4, 14)
        )
        self.cmb_interval = ctk.CTkOptionMenu(
            panel,
            values=["15", "30", "60", "120", "240", "360"],
            width=85,
            height=28,
            font=font_mono(12),
            fg_color=PALETTE["bg_elevated"],
            button_color=PALETTE["lapis"],
        )
        self.cmb_interval.set(str(self.config.get("auto_backup_interval_minutes", 60)))
        self.cmb_interval.grid(row=1, column=2, padx=(0, 12), pady=(4, 14))

        ctk.CTkLabel(panel, text="Manter últimos:", font=font_small(12), text_color=PALETTE["text_secondary"]).grid(
            row=1, column=3, padx=(6, 4), pady=(4, 14)
        )
        self.cmb_keep = ctk.CTkOptionMenu(
            panel,
            values=["5", "10", "15", "25", "50"],
            width=80,
            height=28,
            font=font_mono(12),
            fg_color=PALETTE["bg_elevated"],
            button_color=PALETTE["lapis"],
        )
        self.cmb_keep.set(str(self.config.get("auto_backup_max_keep", 10)))
        self.cmb_keep.grid(row=1, column=4, padx=(0, 12), pady=(4, 14))

        self.var_only_players = ctk.BooleanVar(value=bool(self.config.get("auto_backup_only_with_players", False)))
        ctk.CTkCheckBox(
            panel,
            text="Apenas com jogadores online",
            variable=self.var_only_players,
            font=font_small(11),
            checkbox_width=16,
            checkbox_height=16,
            fg_color=PALETTE["emerald"],
        ).grid(row=1, column=5, padx=6, pady=(4, 14), sticky="w")

        ctk.CTkButton(
            panel,
            text="Salvar Agendamento",
            width=140,
            height=28,
            font=font_small(11, bold=True),
            fg_color=PALETTE["lapis"],
            hover_color=PALETTE["lapis_hover"],
            command=self._save_schedule,
        ).grid(row=1, column=6, padx=(8, 16), pady=(4, 14))

    def _build_backups_list(self) -> None:
        section = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        section.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 8))
        section.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(section, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        hdr.grid_columnconfigure(0, weight=1)

        self.lbl_list_title = ctk.CTkLabel(
            hdr,
            text="Arquivos de Backup Disponíveis",
            font=font_heading(14, bold=True),
            text_color=PALETTE["text_primary"],
        )
        self.lbl_list_title.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            hdr,
            text="Atualizar",
            width=88,
            height=26,
            font=font_small(11),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["border_focus"],
            command=self.refresh_backups,
        ).grid(row=0, column=1, sticky="e")

        self.list_container = ctk.CTkFrame(section, fg_color="transparent")
        self.list_container.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
        self.list_container.grid_columnconfigure(0, weight=1)

    def refresh_backups(self) -> None:
        wname = self.backup_mgr.get_world_name()
        wsize = self.backup_mgr.get_world_size_mb()
        self.lbl_world_info.configure(
            text=f"Mundo Ativo: '{wname}' ({wsize:.2f} MB em disco)   ·   Destino: {self.config.backup_dir.name}/"
        )

        for w in self.list_container.winfo_children():
            w.destroy()

        items = self.backup_mgr.list_backups()
        self.lbl_list_title.configure(text=f"Arquivos de Backup Disponíveis ({len(items)})")

        if not items:
            ctk.CTkLabel(
                self.list_container,
                text="Nenhum backup criado ainda. Clique em 'Criar Backup Agora' para proteger seu mundo.",
                font=font_body(12),
                text_color=PALETTE["text_muted"],
            ).grid(row=0, column=0, pady=18)
            return

        for idx, item in enumerate(items):
            row = ctk.CTkFrame(
                self.list_container,
                fg_color=PALETTE["bg_elevated"],
                corner_radius=5,
                border_width=1,
                border_color=PALETTE["border_subtle"],
            )
            row.grid(row=idx, column=0, sticky="ew", pady=4)
            row.grid_columnconfigure(0, weight=1)

            zpath = Path(item["path"])
            info_txt = f"{item['name']}   ·   {item['size_mb']} MB   ·   Criado em {item['modified']}"
            ctk.CTkLabel(
                row,
                text=info_txt,
                font=font_mono(12),
                text_color=PALETTE["text_primary"],
                anchor="w",
            ).grid(row=0, column=0, padx=12, pady=10, sticky="ew")

            btns = ctk.CTkFrame(row, fg_color="transparent")
            btns.grid(row=0, column=1, padx=10, pady=6)

            ctk.CTkButton(
                btns,
                text="Restaurar Mundo",
                width=120,
                height=28,
                font=font_small(11, bold=True),
                fg_color=PALETTE["copper"],
                hover_color=PALETTE["copper_hover"],
                text_color=PALETTE["text_inverse"],
                command=lambda p=zpath: self._confirm_restore(p),
            ).pack(side="left", padx=4)

            ctk.CTkButton(
                btns,
                text="Excluir",
                width=68,
                height=28,
                font=font_small(11),
                fg_color=PALETTE["bg_surface"],
                hover_color=PALETTE["redstone"],
                command=lambda p=zpath: self._delete_backup(p),
            ).pack(side="left", padx=2)

    def _start_manual_backup(self) -> None:
        tag = self.ent_tag.get().strip() or "manual"
        self.btn_create.configure(state="disabled")
        self.progress.set(0.05)

        def _prog(pct: float, status: str) -> None:
            self.after(0, lambda: self._update_prog_ui(pct, status))

        def _done(ok: bool, msg: str) -> None:
            self.after(0, lambda: self._finish_backup_ui(ok, msg))

        self.backup_mgr.create_backup_async(tag=tag, progress_cb=_prog, done_cb=_done)

    def _update_prog_ui(self, pct: float, status: str) -> None:
        self.progress.set(pct)
        self.lbl_prog_status.configure(text=status)

    def _finish_backup_ui(self, ok: bool, msg: str) -> None:
        self.btn_create.configure(state="normal")
        self.progress.set(1.0 if ok else 0.0)
        self.lbl_prog_status.configure(text=msg)
        self.refresh_backups()
        self.notify_cb(msg, "success" if ok else "error")

    def _confirm_restore(self, zip_path: Path) -> None:
        if self.process_mgr.is_running():
            self.notify_cb("Pare o servidor antes de restaurar um backup.", "warning")
            return

        ans = messagebox.askyesno(
            "Confirmar Restauração de Mundo",
            f"Deseja restaurar o backup '{zip_path.name}'?\n\n"
            "O mundo atual será salvo automaticamente em um arquivo '_pre-restauracao.zip' antes da substituição.",
        )
        if not ans:
            return

        self.lbl_prog_status.configure(text=f"Restaurando {zip_path.name}...")
        self.progress.set(0.5)

        def _done(ok: bool, msg: str) -> None:
            self.after(0, lambda: self._finish_backup_ui(ok, msg))

        self.backup_mgr.restore_backup_async(zip_path, done_cb=_done)

    def _delete_backup(self, zip_path: Path) -> None:
        ok, msg = self.backup_mgr.delete_backup(zip_path)
        self.refresh_backups()
        self.notify_cb(msg, "info" if ok else "error")

    def _save_schedule(self) -> None:
        self.config.set("auto_backup_enabled", bool(self.var_auto_enabled.get()), auto_save=False)
        self.config.set("auto_backup_interval_minutes", int(self.cmb_interval.get()), auto_save=False)
        self.config.set("auto_backup_max_keep", int(self.cmb_keep.get()), auto_save=False)
        self.config.set("auto_backup_only_with_players", bool(self.var_only_players.get()), auto_save=True)
        state_str = "ativado" if self.var_auto_enabled.get() else "desativado"
        self.notify_cb(f"Agendamento de backup {state_str} (a cada {self.cmb_interval.get()} min).", "success")

    def _open_backup_folder(self) -> None:
        try:
            os.startfile(str(self.config.backup_dir))
        except Exception as exc:
            self.notify_cb(f"Erro ao abrir pasta: {exc}", "error")
