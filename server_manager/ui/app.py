"""
Janela Principal do Obsidian Deck — Minecraft Vanilla Server Manager.
Integra Barra de Comando Persistente, Menu Lateral e Views Modulares.
"""

from __future__ import annotations
from datetime import datetime
from tkinter import messagebox
from typing import Dict, List, Tuple
import customtkinter as ctk

from ..backup_manager import BackupManager
from ..config import ConfigManager
from ..player_manager import PlayerManager
from ..process_manager import ServerProcessManager, ServerState
from ..properties_manager import ServerPropertiesManager
from ..theme import PALETTE, font_body, font_display, font_heading, font_mono, font_small, get_icon
from .views.automation_view import AutomationView
from .views.backups_view import BackupsView
from .views.console_view import ConsoleView
from .views.dashboard_view import DashboardView
from .views.files_view import FilesAndEnvView
from .views.players_view import PlayersView
from .views.properties_view import PropertiesView


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class MinecraftServerManagerApp(ctk.CTk):
    """Aplicação principal com arquitetura reativa baseada em filas e baixo uso de CPU."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Obsidian Deck — Minecraft Vanilla Server Manager")
        self.geometry("1260x780")
        self.minsize(1040, 660)
        self.configure(fg_color=PALETTE["bg_root"])

        # Inicializar controladores de domínio
        self.config_mgr = ConfigManager()
        self.props_mgr = ServerPropertiesManager(self.config_mgr.server_dir)
        self.process_mgr = ServerProcessManager(self.config_mgr)
        self.player_mgr = PlayerManager(self.config_mgr, self.process_mgr)
        self.backup_mgr = BackupManager(self.config_mgr, self.process_mgr, self.props_mgr)

        self.active_tab: str = "dashboard"
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}
        self.views: Dict[str, ctk.CTkBaseClass] = {}
        self._last_scheduled_restart_date: str = ""
        self._is_closing: bool = False

        # Layout raiz: Sidebar (col 0) + Área Principal (col 1)
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main_workspace()
        self.select_tab("dashboard")

        # Protocolo de fechamento seguro
        self.protocol("WM_DELETE_WINDOW", self._on_close_window)

        # Auto-start do servidor se configurado
        if self.config_mgr.get("auto_start_server_on_launch", False):
            self.after(600, self._action_start_server)

        # Loops periódicos leves
        self.after(200, self._drain_queues_loop)
        self.after(1000, self._telemetry_and_scheduler_loop)

    # -----------------------------------------------------------------------
    # Construção do Menu Lateral (Sidebar)
    # -----------------------------------------------------------------------
    def _build_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(
            self,
            width=225,
            fg_color=PALETTE["bg_sidebar"],
            corner_radius=0,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_columnconfigure(0, weight=1)
        self.sidebar.grid_rowconfigure(9, weight=1)

        # Marca / Cabeçalho
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(20, 18))

        icon_lbl = ctk.CTkLabel(
            brand,
            text="",
            image=get_icon("cube", size=26, color=PALETTE["emerald"]),
        )
        icon_lbl.grid(row=0, column=0, rowspan=2, padx=(0, 10))

        ctk.CTkLabel(
            brand,
            text="Obsidian Deck",
            font=font_display(17, bold=True),
            text_color=PALETTE["text_primary"],
            anchor="w",
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            brand,
            text="Vanilla Server Control",
            font=font_small(11),
            text_color=PALETTE["text_muted"],
            anchor="w",
        ).grid(row=1, column=1, sticky="w")

        nav_items = [
            ("dashboard", "Visão Geral", "dashboard"),
            ("console", "Console ao Vivo", "console"),
            ("players", "Jogadores & OP", "players"),
            ("properties", "Configurações", "properties"),
            ("backups", "Backups do Mundo", "backups"),
            ("automation", "Automação", "automation"),
            ("files", "Arquivos & Java", "files"),
        ]

        for idx, (key, label, icon_name) in enumerate(nav_items, start=1):
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {label}",
                image=get_icon(icon_name, size=18, color=PALETTE["text_secondary"]),
                compound="left",
                anchor="w",
                height=40,
                corner_radius=6,
                font=font_body(13, bold=True),
                fg_color="transparent",
                hover_color=PALETTE["bg_elevated"],
                text_color=PALETTE["text_secondary"],
                command=lambda k=key: self.select_tab(k),
            )
            btn.grid(row=idx, column=0, sticky="ew", padx=12, pady=3)
            self.nav_buttons[key] = btn

        # Rodapé da Sidebar: Resumo rápido do diretório e versão
        footer = ctk.CTkFrame(
            self.sidebar,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        footer.grid(row=10, column=0, sticky="ew", padx=12, pady=14)
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_sidebar_folder = ctk.CTkLabel(
            footer,
            text=f"Pasta: {self.config_mgr.server_dir.name}",
            font=font_small(11, bold=True),
            text_color=PALETTE["text_primary"],
            anchor="w",
        )
        self.lbl_sidebar_folder.grid(row=0, column=0, padx=10, pady=(8, 1), sticky="ew")

        self.lbl_sidebar_jar = ctk.CTkLabel(
            footer,
            text=f"JAR: {self.config_mgr.get('jar_file', 'server.jar')} · MC {self.process_mgr.server_version}",
            font=font_mono(10),
            text_color=PALETTE["text_muted"],
            anchor="w",
        )
        self.lbl_sidebar_jar.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")

    # -----------------------------------------------------------------------
    # Área Principal (Header de Comando + Barra de Notificação + Views)
    # -----------------------------------------------------------------------
    def _build_main_workspace(self) -> None:
        self.workspace = ctk.CTkFrame(self, fg_color=PALETTE["bg_root"], corner_radius=0)
        self.workspace.grid(row=0, column=1, sticky="nsew")
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(2, weight=1)

        # 1. Barra de Comando Superior Persistente
        self.header = ctk.CTkFrame(
            self.workspace,
            fg_color=PALETTE["bg_header"],
            corner_radius=0,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.grid_columnconfigure(1, weight=1)

        # Badge de Status
        status_wrap = ctk.CTkFrame(self.header, fg_color="transparent")
        status_wrap.grid(row=0, column=0, padx=(18, 12), pady=12, sticky="w")

        self.lbl_status_badge = ctk.CTkLabel(
            status_wrap,
            text=" ● OFFLINE ",
            font=font_mono(12, bold=True),
            fg_color=PALETTE["bg_elevated"],
            text_color=PALETTE["text_secondary"],
            corner_radius=5,
            padx=10,
            pady=4,
        )
        self.lbl_status_badge.pack(side="left", padx=(0, 10))

        # Informações rápidas de conexão
        info_wrap = ctk.CTkFrame(self.header, fg_color="transparent")
        info_wrap.grid(row=0, column=1, pady=10, sticky="ew")

        self.lbl_header_title = ctk.CTkLabel(
            info_wrap,
            text="Servidor Minecraft Vanilla",
            font=font_heading(14, bold=True),
            text_color=PALETTE["text_primary"],
            anchor="w",
        )
        self.lbl_header_title.pack( anchor="w")

        self.lbl_header_sub = ctk.CTkLabel(
            info_wrap,
            text="127.0.0.1:25565 · Uptime 00:00:00 · 0 Jogadores",
            font=font_mono(11),
            text_color=PALETTE["text_secondary"],
            anchor="w",
        )
        self.lbl_header_sub.pack(anchor="w")

        # Botões Globais de Controle do Processo
        ctrl_bar = ctk.CTkFrame(self.header, fg_color="transparent")
        ctrl_bar.grid(row=0, column=2, padx=18, pady=12, sticky="e")

        self.btn_start = ctk.CTkButton(
            ctrl_bar,
            text="Iniciar Servidor",
            image=get_icon("play", size=14, color=PALETTE["text_inverse"]),
            compound="left",
            command=self._action_start_server,
            font=font_body(12, bold=True),
            fg_color=PALETTE["emerald"],
            hover_color=PALETTE["emerald_hover"],
            text_color=PALETTE["text_inverse"],
            height=34,
            width=142,
            corner_radius=5,
        )
        self.btn_start.pack(side="left", padx=4)

        self.btn_restart = ctk.CTkButton(
            ctrl_bar,
            text="Reiniciar",
            image=get_icon("restart", size=14, color=PALETTE["text_primary"]),
            compound="left",
            command=self._action_restart_server,
            font=font_body(12, bold=True),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["copper"],
            text_color=PALETTE["text_primary"],
            height=34,
            width=108,
            corner_radius=5,
        )
        self.btn_restart.pack(side="left", padx=4)

        self.btn_stop = ctk.CTkButton(
            ctrl_bar,
            text="Parar Seguro",
            image=get_icon("stop", size=14, color="#FFFFFF"),
            compound="left",
            command=self._action_stop_server,
            font=font_body(12, bold=True),
            fg_color=PALETTE["redstone"],
            hover_color=PALETTE["redstone_hover"],
            text_color="#FFFFFF",
            height=34,
            width=128,
            corner_radius=5,
        )
        self.btn_stop.pack(side="left", padx=(4, 0))

        # 2. Faixa de Notificação de Eventos em Tempo Real
        self.notif_bar = ctk.CTkFrame(
            self.workspace,
            fg_color=PALETTE["bg_surface"],
            corner_radius=0,
            height=28,
        )
        self.notif_bar.grid(row=1, column=0, sticky="ew")
        self.notif_bar.grid_columnconfigure(1, weight=1)

        self.notif_dot = ctk.CTkLabel(
            self.notif_bar,
            text="●",
            font=font_mono(12, bold=True),
            text_color=PALETTE["emerald"],
        )
        self.notif_dot.grid(row=0, column=0, padx=(18, 6), pady=3)

        self.lbl_notif = ctk.CTkLabel(
            self.notif_bar,
            text=f"Diretório carregado: {self.config_mgr.server_dir} (Mundos e configurações preservados).",
            font=font_small(11),
            text_color=PALETTE["text_secondary"],
            anchor="w",
        )
        self.lbl_notif.grid(row=0, column=1, sticky="ew", pady=3)

        # 3. Container de Views
        self.view_container = ctk.CTkFrame(self.workspace, fg_color="transparent")
        self.view_container.grid(row=2, column=0, sticky="nsew", padx=14, pady=10)
        self.view_container.grid_columnconfigure(0, weight=1)
        self.view_container.grid_rowconfigure(0, weight=1)

        # Instanciar Views
        self.dashboard_view = DashboardView(
            self.view_container,
            self.config_mgr,
            self.process_mgr,
            self.props_mgr,
            self.show_notification,
        )
        self.console_view = ConsoleView(
            self.view_container,
            self.config_mgr,
            self.process_mgr,
            self.show_notification,
        )
        self.players_view = PlayersView(
            self.view_container,
            self.player_mgr,
            self.process_mgr,
            self.show_notification,
        )
        self.properties_view = PropertiesView(
            self.view_container,
            self.props_mgr,
            self.process_mgr,
            self.show_notification,
        )
        self.backups_view = BackupsView(
            self.view_container,
            self.config_mgr,
            self.backup_mgr,
            self.process_mgr,
            self.show_notification,
        )
        self.automation_view = AutomationView(
            self.view_container,
            self.config_mgr,
            self.process_mgr,
            self.show_notification,
        )
        self.files_view = FilesAndEnvView(
            self.view_container,
            self.config_mgr,
            self.process_mgr,
            self.props_mgr,
            self._on_server_directory_changed,
            self.show_notification,
        )

        self.views = {
            "dashboard": self.dashboard_view,
            "console": self.console_view,
            "players": self.players_view,
            "properties": self.properties_view,
            "backups": self.backups_view,
            "automation": self.automation_view,
            "files": self.files_view,
        }

        self._refresh_header_summary()

    # -----------------------------------------------------------------------
    # Navegação entre telas
    # -----------------------------------------------------------------------
    def select_tab(self, tab_key: str) -> None:
        if tab_key not in self.views:
            return
        self.active_tab = tab_key

        for k, btn in self.nav_buttons.items():
            is_sel = k == tab_key
            btn.configure(
                fg_color=PALETTE["bg_glass"] if is_sel else "transparent",
                text_color=PALETTE["text_primary"] if is_sel else PALETTE["text_secondary"],
                image=get_icon(
                    k,
                    size=18,
                    color=PALETTE["emerald"] if is_sel else PALETTE["text_secondary"],
                ),
            )

        for k, view in self.views.items():
            if k == tab_key:
                view.grid(row=0, column=0, sticky="nsew")
            else:
                view.grid_forget()

        if tab_key == "players":
            self.players_view.refresh_all()
        elif tab_key == "backups":
            self.backups_view.refresh_backups()
        elif tab_key == "files":
            self.files_view.refresh_file_tree()

    # -----------------------------------------------------------------------
    # Ações de Controle do Servidor
    # -----------------------------------------------------------------------
    def _action_start_server(self) -> None:
        ok, msg = self.process_mgr.start_server()
        self.show_notification(msg, "success" if ok else "warning")
        self._refresh_header_summary()

    def _action_stop_server(self) -> None:
        if not self.process_mgr.is_running():
            self.show_notification("O servidor já está desligado.", "info")
            return
        self.show_notification("Salvando mundos (save-all) e encerrando servidor com segurança...", "warning")
        self.process_mgr.stop_server(
            force=False,
            callback=lambda _ok, m: self.after(0, lambda: self.show_notification(m, "info")),
        )
        self._refresh_header_summary()

    def _action_restart_server(self) -> None:
        self.show_notification("Reiniciando o servidor com salvamento seguro...", "warning")
        self.process_mgr.restart_server(
            callback=lambda ok, m: self.after(
                0, lambda: self.show_notification(m, "success" if ok else "error")
            )
        )

    def show_notification(self, message: str, level: str = "info") -> None:
        color_map = {
            "success": PALETTE["emerald"],
            "warning": PALETTE["copper"],
            "error": PALETTE["redstone"],
            "info": PALETTE["lapis"],
        }
        col = color_map.get(level, PALETTE["lapis"])
        ts = datetime.now().strftime("%H:%M:%S")
        self.notif_dot.configure(text_color=col)
        self.lbl_notif.configure(text=f"[{ts}] {message}", text_color=PALETTE["text_primary"])

    def _on_server_directory_changed(self) -> None:
        self.lbl_sidebar_folder.configure(text=f"Pasta: {self.config_mgr.server_dir.name}")
        self.lbl_sidebar_jar.configure(
            text=f"JAR: {self.config_mgr.get('jar_file', 'server.jar')} · MC {self.process_mgr.server_version}"
        )
        self.dashboard_view.refresh_static_info()
        self.properties_view.reload_from_disk()
        self.players_view.refresh_all()
        self.backups_view.refresh_backups()
        self._refresh_header_summary()

    def _refresh_header_summary(self) -> None:
        state = self.process_mgr.state
        running = self.process_mgr.is_running()

        badge_styles = {
            ServerState.ONLINE: (PALETTE["emerald_dim"], PALETTE["emerald"], " ● ONLINE "),
            ServerState.STARTING: (PALETTE["copper_dim"], PALETTE["copper"], " ◐ INICIANDO "),
            ServerState.STOPPING: (PALETTE["copper_dim"], PALETTE["copper"], " ◐ PARANDO "),
            ServerState.CRASHED: (PALETTE["redstone_dim"], PALETTE["redstone"], " ✖ FALHA "),
            ServerState.OFFLINE: (PALETTE["bg_elevated"], PALETTE["text_secondary"], " ● OFFLINE "),
        }
        bg_c, fg_c, txt = badge_styles.get(state, badge_styles[ServerState.OFFLINE])
        self.lbl_status_badge.configure(fg_color=bg_c, text_color=fg_c, text=txt)

        motd_raw = self.props_mgr.values.get("motd", "Servidor Minecraft Vanilla")
        # Limpar códigos de formatação §x para leitura limpa no cabeçalho
        clean_motd = motd_raw.replace("\\n", " · ")
        for code in ("§0", "§1", "§2", "§3", "§4", "§5", "§6", "§7", "§8", "§9", "§a", "§b", "§c", "§d", "§e", "§f", "§r", "§l", "§o", "§n", "§k"):
            clean_motd = clean_motd.replace(code, "")

        port = self.props_mgr.values.get("server-port", "25565")
        max_p = self.props_mgr.values.get("max-players", "20")
        online_n = len(self.process_mgr.online_players)
        uptime = self.process_mgr.get_uptime_formatted()
        ram_mb = int(self.process_mgr.current_ram_mb)
        xmx_mb = int(self.config_mgr.get("xmx_mb", 4096))

        self.lbl_header_title.configure(text=clean_motd.strip() or "Servidor Minecraft Vanilla")
        self.lbl_header_sub.configure(
            text=f"127.0.0.1:{port}   ·   Uptime: {uptime}   ·   Jogadores: {online_n}/{max_p}   ·   RAM: {ram_mb}/{xmx_mb} MB"
        )

        self.btn_start.configure(state="disabled" if running else "normal")
        self.btn_stop.configure(state="normal" if running else "disabled")

    # -----------------------------------------------------------------------
    # Loops Assíncronos de Baixo Consumo
    # -----------------------------------------------------------------------
    def _drain_queues_loop(self) -> None:
        if self._is_closing:
            return

        # 1. Drenar linhas de console em lote (máx 80 por ciclo para fluidez)
        batch: List[Tuple[str, str]] = []
        while not self.process_mgr.log_queue.empty() and len(batch) < 80:
            try:
                batch.append(self.process_mgr.log_queue.get_nowait())
            except Exception:
                break
        if batch:
            self.console_view.append_log_lines(batch)

        # 2. Drenar eventos semânticos (join, leave, online, crash, etc.)
        had_events = False
        while not self.process_mgr.event_queue.empty():
            try:
                ev = self.process_mgr.event_queue.get_nowait()
                had_events = True
                self.show_notification(f"{ev['category']}: {ev['message']}", ev.get("level", "info"))
            except Exception:
                break

        if had_events:
            self.dashboard_view.refresh_events_feed()
            if self.active_tab == "players":
                self.players_view.refresh_all()

        self.after(200, self._drain_queues_loop)

    def _telemetry_and_scheduler_loop(self) -> None:
        if self._is_closing:
            return

        self.process_mgr.sample_telemetry()
        self._refresh_header_summary()
        self.dashboard_view.update_live_telemetry()

        # Verificar backups automáticos agendados
        self.backup_mgr.check_scheduled_backup()

        # Verificar reinicialização diária agendada
        if self.config_mgr.get("scheduled_restart_enabled", False) and self.process_mgr.is_running():
            target_hm = str(self.config_mgr.get("scheduled_restart_time", "04:00")).strip()
            now = datetime.now()
            now_hm = now.strftime("%H:%M")
            today_str = now.strftime("%Y-%m-%d")
            if now_hm == target_hm and self._last_scheduled_restart_date != today_str:
                self._last_scheduled_restart_date = today_str
                self.process_mgr.send_command("say [Servidor] Reinicializacao programada iniciando agora!")
                self._action_restart_server()

        self.after(1000, self._telemetry_and_scheduler_loop)

    # -----------------------------------------------------------------------
    # Encerramento Seguro da Janela
    # -----------------------------------------------------------------------
    def _on_close_window(self) -> None:
        if self.process_mgr.is_running():
            if self.config_mgr.get("safe_stop_on_exit", True):
                ans = messagebox.askyesnocancel(
                    "Servidor em Execução",
                    "O servidor Minecraft ainda está online.\n\n"
                    "• Clique em SIM para salvar o mundo (save-all), parar o servidor com segurança e sair.\n"
                    "• Clique em NÃO para fechar apenas o gerenciador (não recomendado).\n"
                    "• Clique em CANCELAR para voltar ao gerenciador.",
                )
                if ans is None:
                    return
                if ans is True:
                    self._is_closing = True
                    self.show_notification("Salvando mundos e encerrando servidor antes de sair...", "warning")
                    self.process_mgr.stop_server(
                        force=False,
                        callback=lambda _ok, _m: self.after(0, self.destroy),
                    )
                    return

        self._is_closing = True
        self.destroy()
