"""
Gerenciador de Diretório do Servidor, Localizador de Java e Explorador/Editor de Arquivos.
Suporta leitura e edição de arquivos de configuração e descompactação em memória de logs (.log.gz).
"""

from __future__ import annotations
from datetime import datetime
import gzip
import os
from pathlib import Path
from tkinter import filedialog
from typing import Callable, Optional
import customtkinter as ctk

from ...config import ConfigManager
from ...process_manager import ServerProcessManager
from ...properties_manager import ServerPropertiesManager
from ...theme import PALETTE, font_body, font_heading, font_mono, font_small


class FilesAndEnvView(ctk.CTkFrame):
    """Gerencia o diretório do servidor, instalação do Java e arquivos locais."""

    EDITABLE_EXTS = {".properties", ".json", ".txt", ".bat", ".cmd", ".log", ".yml", ".yaml", ".conf"}

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        config: ConfigManager,
        process_mgr: ServerProcessManager,
        props_mgr: ServerPropertiesManager,
        on_dir_changed_cb: Callable[[], None],
        notify_cb: Callable[[str, str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.config = config
        self.process_mgr = process_mgr
        self.props_mgr = props_mgr
        self.on_dir_changed_cb = on_dir_changed_cb
        self.notify_cb = notify_cb

        self.current_file: Optional[Path] = None
        self.current_file_readonly: bool = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_environment_card()
        self._build_explorer_split()
        self.refresh_file_tree()
        self._verify_java_silent()

    def _build_environment_card(self) -> None:
        card = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        card.grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 8))
        card.grid_columnconfigure(1, weight=1)

        # Linha 0: Diretório do Servidor
        ctk.CTkLabel(
            card,
            text="Diretório do Servidor:",
            font=font_heading(12, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=0, column=0, padx=(14, 8), pady=(12, 6), sticky="w")

        self.ent_server_dir = ctk.CTkEntry(
            card,
            height=30,
            font=font_mono(11),
            fg_color=PALETTE["bg_console"],
            border_color=PALETTE["border_default"],
        )
        self.ent_server_dir.insert(0, str(self.config.server_dir))
        self.ent_server_dir.grid(row=0, column=1, sticky="ew", padx=4, pady=(12, 6))

        ctk.CTkButton(
            card,
            text="Selecionar Pasta...",
            width=130,
            height=30,
            font=font_small(11, bold=True),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["border_focus"],
            command=self._browse_server_dir,
        ).grid(row=0, column=2, padx=4, pady=(12, 6))

        ctk.CTkButton(
            card,
            text="Abrir no Explorer",
            width=125,
            height=30,
            font=font_small(11),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["border_focus"],
            command=self._open_in_explorer,
        ).grid(row=0, column=3, padx=(4, 14), pady=(12, 6))

        # Linha 1: Executável Java e Arquivo JAR
        ctk.CTkLabel(
            card,
            text="Runtime Java (JVM):",
            font=font_heading(12, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=1, column=0, padx=(14, 8), pady=(4, 12), sticky="w")

        java_row = ctk.CTkFrame(card, fg_color="transparent")
        java_row.grid(row=1, column=1, sticky="ew", padx=4, pady=(4, 12))
        java_row.grid_columnconfigure(0, weight=1)

        discovered_javas = self.config.discover_all_javas()
        cur_java = str(self.config.get("java_path", "java"))
        if cur_java not in discovered_javas:
            discovered_javas.insert(0, cur_java)

        self.cmb_java = ctk.CTkComboBox(
            java_row,
            values=discovered_javas,
            height=30,
            font=font_mono(11),
            fg_color=PALETTE["bg_console"],
            border_color=PALETTE["border_default"],
            button_color=PALETTE["lapis"],
            command=lambda _v: self._apply_java_selection(),
        )
        self.cmb_java.set(cur_java)
        self.cmb_java.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.lbl_java_ver = ctk.CTkLabel(
            java_row,
            text="Verificando Java...",
            font=font_mono(11),
            text_color=PALETTE["text_secondary"],
        )
        self.lbl_java_ver.grid(row=0, column=1, padx=4)

        ctk.CTkButton(
            card,
            text="Localizar java.exe...",
            width=130,
            height=30,
            font=font_small(11),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["border_focus"],
            command=self._browse_java_exe,
        ).grid(row=1, column=2, padx=4, pady=(4, 12))

        ctk.CTkButton(
            card,
            text="Testar Java",
            width=125,
            height=30,
            font=font_small(11, bold=True),
            fg_color=PALETTE["lapis"],
            hover_color=PALETTE["lapis_hover"],
            command=self._test_java_btn,
        ).grid(row=1, column=3, padx=(4, 14), pady=(4, 12))

    def _build_explorer_split(self) -> None:
        split = ctk.CTkFrame(self, fg_color="transparent")
        split.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        split.grid_columnconfigure(0, weight=5)
        split.grid_columnconfigure(1, weight=7)
        split.grid_rowconfigure(0, weight=1)

        # Painel Esquerdo: Lista de Arquivos do Servidor + Logs
        left = ctk.CTkFrame(
            split,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        lhdr = ctk.CTkFrame(left, fg_color="transparent")
        lhdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        lhdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            lhdr,
            text="Arquivos do Servidor & Logs",
            font=font_heading(13, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            lhdr,
            text="Atualizar",
            width=76,
            height=24,
            font=font_small(11),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["border_focus"],
            command=self.refresh_file_tree,
        ).grid(row=0, column=1, sticky="e")

        self.file_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.file_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 10))
        self.file_scroll.grid_columnconfigure(0, weight=1)

        # Painel Direito: Visualizador e Editor de Arquivo Integrado
        right = ctk.CTkFrame(
            split,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        rhdr = ctk.CTkFrame(right, fg_color="transparent")
        rhdr.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        rhdr.grid_columnconfigure(0, weight=1)

        self.lbl_editor_title = ctk.CTkLabel(
            rhdr,
            text="Selecione um arquivo à esquerda para inspecionar ou editar",
            font=font_mono(12, bold=True),
            text_color=PALETTE["text_secondary"],
            anchor="w",
        )
        self.lbl_editor_title.grid(row=0, column=0, sticky="ew")

        self.btn_save_file = ctk.CTkButton(
            rhdr,
            text="Salvar Arquivo",
            width=115,
            height=26,
            font=font_small(11, bold=True),
            fg_color=PALETTE["emerald"],
            hover_color=PALETTE["emerald_hover"],
            text_color=PALETTE["text_inverse"],
            state="disabled",
            command=self._save_current_file,
        )
        self.btn_save_file.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.editor_box = ctk.CTkTextbox(
            right,
            fg_color=PALETTE["bg_console"],
            text_color=PALETTE["text_primary"],
            font=font_mono(12),
            wrap="none",
            border_width=1,
            border_color=PALETTE["border_subtle"],
            corner_radius=4,
        )
        self.editor_box.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

    def refresh_file_tree(self) -> None:
        for w in self.file_scroll.winfo_children():
            w.destroy()

        srv_dir = self.config.server_dir
        if not srv_dir.exists():
            return

        entries = sorted(
            srv_dir.iterdir(),
            key=lambda p: (not p.is_dir(), p.name.lower()),
        )

        row_idx = 0
        for item in entries:
            if item.name.startswith(".") or item.name == "__pycache__":
                continue
            self._render_file_entry(row_idx, item, prefix="")
            row_idx += 1

        # Também listar arquivos dentro de logs/ para facilitar leitura de histórico
        logs_dir = srv_dir / "logs"
        if logs_dir.exists():
            for log_f in sorted(logs_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
                if log_f.is_file():
                    self._render_file_entry(row_idx, log_f, prefix="logs/")
                    row_idx += 1

    def _render_file_entry(self, row_idx: int, path: Path, prefix: str = "") -> None:
        is_dir = path.is_dir()
        row = ctk.CTkFrame(
            self.file_scroll,
            fg_color=PALETTE["bg_elevated"],
            corner_radius=4,
        )
        row.grid(row=row_idx, column=0, sticky="ew", pady=2)
        row.grid_columnconfigure(0, weight=1)

        try:
            st = path.stat()
            if is_dir:
                size_str = "<PASTA>"
            elif st.st_size >= 1024 * 1024:
                size_str = f"{st.st_size / (1024 * 1024):.1f} MB"
            elif st.st_size >= 1024:
                size_str = f"{st.st_size / 1024:.1f} KB"
            else:
                size_str = f"{st.st_size} B"
            dt_str = datetime.fromtimestamp(st.st_mtime).strftime("%d/%m %H:%M")
        except Exception:
            size_str = "-"
            dt_str = "-"

        display_name = f"{prefix}{path.name}/" if is_dir else f"{prefix}{path.name}"
        color = PALETTE["lapis"] if is_dir else (PALETTE["emerald"] if path.name == "server.jar" else PALETTE["text_primary"])

        ctk.CTkLabel(
            row,
            text=f"{display_name}   ({size_str} · {dt_str})",
            font=font_mono(11, bold=is_dir or path.name == "server.jar"),
            text_color=color,
            anchor="w",
        ).grid(row=0, column=0, padx=10, pady=5, sticky="ew")

        if is_dir:
            ctk.CTkButton(
                row,
                text="Abrir",
                width=58,
                height=22,
                font=font_small(10),
                fg_color=PALETTE["bg_surface"],
                hover_color=PALETTE["border_focus"],
                command=lambda p=path: os.startfile(str(p)),
            ).grid(row=0, column=1, padx=6, pady=4)
        elif path.suffix.lower() in self.EDITABLE_EXTS or path.name.endswith(".log.gz"):
            lbl = "Ler Log" if path.name.endswith(".log.gz") else "Editar/Ver"
            ctk.CTkButton(
                row,
                text=lbl,
                width=72,
                height=22,
                font=font_small(10),
                fg_color=PALETTE["bg_surface"],
                hover_color=PALETTE["lapis"],
                command=lambda p=path: self._open_file_in_editor(p),
            ).grid(row=0, column=1, padx=6, pady=4)
        elif path.suffix.lower() == ".jar":
            ctk.CTkButton(
                row,
                text="Usar JAR",
                width=72,
                height=22,
                font=font_small(10),
                fg_color=PALETTE["emerald"] if path.name == self.config.get("jar_file") else PALETTE["bg_surface"],
                text_color=PALETTE["text_inverse"] if path.name == self.config.get("jar_file") else PALETTE["text_primary"],
                command=lambda p=path: self._select_jar_file(p),
            ).grid(row=0, column=1, padx=6, pady=4)

    def _open_file_in_editor(self, path: Path) -> None:
        try:
            if path.name.endswith(".log.gz"):
                with gzip.open(path, "rt", encoding="utf-8", errors="replace") as gz:
                    content = gz.read()
                self.current_file = path
                self.current_file_readonly = True
                self.lbl_editor_title.configure(
                    text=f"Visualizando arquivo compactado: {path.name} (Somente Leitura)",
                    text_color=PALETTE["copper"],
                )
                self.btn_save_file.configure(state="disabled")
            else:
                content = path.read_text(encoding="utf-8", errors="replace")
                self.current_file = path
                self.current_file_readonly = False
                self.lbl_editor_title.configure(
                    text=f"Editando: {path.relative_to(self.config.server_dir)}",
                    text_color=PALETTE["emerald"],
                )
                self.btn_save_file.configure(state="normal")

            self.editor_box.configure(state="normal")
            self.editor_box.delete("1.0", "end")
            self.editor_box.insert("1.0", content)
            if self.current_file_readonly:
                self.editor_box.configure(state="disabled")
        except Exception as exc:
            self.notify_cb(f"Não foi possível abrir {path.name}: {exc}", "error")

    def _save_current_file(self) -> None:
        if not self.current_file or self.current_file_readonly:
            return
        try:
            text = self.editor_box.get("1.0", "end-1c")
            self.current_file.write_text(text, encoding="utf-8")
            if self.current_file.name == "server.properties":
                self.props_mgr.load()
            self.notify_cb(f"Arquivo '{self.current_file.name}' salvo com sucesso.", "success")
        except Exception as exc:
            self.notify_cb(f"Erro ao salvar arquivo: {exc}", "error")

    def _select_jar_file(self, jar_path: Path) -> None:
        self.config.set("jar_file", jar_path.name)
        self.refresh_file_tree()
        self.notify_cb(f"Arquivo executável do servidor definido como '{jar_path.name}'.", "success")

    def _browse_server_dir(self) -> None:
        chosen = filedialog.askdirectory(
            title="Selecionar Pasta do Servidor Minecraft",
            initialdir=str(self.config.server_dir),
        )
        if not chosen:
            return
        new_dir = Path(chosen).resolve()
        self.config.set("server_dir", str(new_dir))
        self.ent_server_dir.delete(0, "end")
        self.ent_server_dir.insert(0, str(new_dir))
        self.props_mgr.set_server_dir(new_dir)
        self.refresh_file_tree()
        self.on_dir_changed_cb()
        self.notify_cb(f"Diretório do servidor alterado para: {new_dir}", "success")

    def _browse_java_exe(self) -> None:
        chosen = filedialog.askopenfilename(
            title="Localizar Executável do Java (java.exe)",
            filetypes=[("Executável Java", "java.exe"), ("Todos os arquivos", "*.*")],
        )
        if not chosen:
            return
        self.cmb_java.set(chosen)
        self._apply_java_selection()

    def _apply_java_selection(self) -> None:
        java_exec = self.cmb_java.get().strip() or "java"
        self.config.set("java_path", java_exec)
        self._verify_java_silent()

    def _verify_java_silent(self) -> None:
        java_exec = self.cmb_java.get().strip() or "java"
        ok, desc = self.config.test_java_version(java_exec)
        self.lbl_java_ver.configure(
            text=f"✓ {desc[:42]}" if ok else "✗ Java não encontrado",
            text_color=PALETTE["emerald"] if ok else PALETTE["redstone"],
        )

    def _test_java_btn(self) -> None:
        java_exec = self.cmb_java.get().strip() or "java"
        self.config.set("java_path", java_exec)
        ok, desc = self.config.test_java_version(java_exec)
        self._verify_java_silent()
        self.notify_cb(f"Teste de Java: {desc}", "success" if ok else "error")

    def _open_in_explorer(self) -> None:
        try:
            os.startfile(str(self.config.server_dir))
        except Exception as exc:
            self.notify_cb(f"Não foi possível abrir o Explorer: {exc}", "error")
