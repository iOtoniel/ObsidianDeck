"""
Visão Geral (Dashboard) e Controle de Memória JVM:
- Status em tempo real, Jogadores Online, Tempo de Atividade, CPU e RAM
- Gráficos de osciloscópio duplos (CPU % e Memória RAM MB)
- Configuração rápida de memória RAM (-Xms e -Xmx) e ações imediatas do mundo
"""

from __future__ import annotations
from typing import Callable
import customtkinter as ctk

from ...config import ConfigManager
from ...process_manager import ServerProcessManager, ServerState
from ...properties_manager import ServerPropertiesManager
from ...theme import PALETTE, font_body, font_heading, font_mono, font_small
from ..components import MetricTile, TelemetryOscilloscope


class DashboardView(ctk.CTkScrollableFrame):
    """Painel principal de telemetria, controle de RAM e eventos recentes."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        config: ConfigManager,
        process_mgr: ServerProcessManager,
        props_mgr: ServerPropertiesManager,
        notify_cb: Callable[[str, str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.config = config
        self.process_mgr = process_mgr
        self.props_mgr = props_mgr
        self.notify_cb = notify_cb

        self.grid_columnconfigure(0, weight=1)

        self._build_top_metrics()
        self._build_telemetry_charts()
        self._build_bottom_panels()
        self.refresh_static_info()

    def _build_top_metrics(self) -> None:
        strip = ctk.CTkFrame(self, fg_color="transparent")
        strip.grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 10))
        for col in range(4):
            strip.grid_columnconfigure(col, weight=1, uniform="metric")

        self.tile_status = MetricTile(
            strip,
            label="Estado do Servidor",
            value="OFFLINE",
            subtext="Porta 25565 · Vanilla",
            accent_color=PALETTE["text_muted"],
        )
        self.tile_status.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self.tile_players = MetricTile(
            strip,
            label="Jogadores Conectados",
            value="0 / 2",
            subtext="Nenhum jogador online",
            accent_color=PALETTE["lapis"],
        )
        self.tile_players.grid(row=0, column=1, sticky="nsew", padx=6)

        self.tile_uptime = MetricTile(
            strip,
            label="Tempo de Atividade",
            value="00:00:00",
            subtext="Aguardando inicialização",
            accent_color=PALETTE["amethyst"],
        )
        self.tile_uptime.grid(row=0, column=2, sticky="nsew", padx=6)

        self.tile_resources = MetricTile(
            strip,
            label="Consumo Java (CPU / RAM)",
            value="0.0% · 0 MB",
            subtext="Host: 0% CPU",
            accent_color=PALETTE["copper"],
        )
        self.tile_resources.grid(row=0, column=3, sticky="nsew", padx=(6, 0))

    def _build_telemetry_charts(self) -> None:
        charts_frame = ctk.CTkFrame(self, fg_color="transparent")
        charts_frame.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 12))
        charts_frame.grid_columnconfigure(0, weight=1, uniform="chart")
        charts_frame.grid_columnconfigure(1, weight=1, uniform="chart")

        self.chart_cpu = TelemetryOscilloscope(
            charts_frame,
            title="Processamento (CPU % — Processo Java & Host)",
            unit="%",
            line_color=PALETTE["emerald"],
            fill_color="#112A1F",
            max_value=100.0,
            height=175,
        )
        self.chart_cpu.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        max_ram = float(self.config.get("xmx_mb", 4096))
        self.chart_ram = TelemetryOscilloscope(
            charts_frame,
            title="Memória Alocada em Uso (RSS MB vs Limite Xmx)",
            unit="MB",
            line_color=PALETTE["copper"],
            fill_color="#2B1C10",
            max_value=max_ram,
            height=175,
        )
        self.chart_ram.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

    def _build_bottom_panels(self) -> None:
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=2, column=0, sticky="nsew", padx=4, pady=(0, 8))
        bottom.grid_columnconfigure(0, weight=11)
        bottom.grid_columnconfigure(1, weight=9)

        # --- Painel Esquerdo: Controle de Memória RAM e JVM ---
        ram_panel = ctk.CTkFrame(
            bottom,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        ram_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ram_panel.grid_columnconfigure(0, weight=1)

        hdr_ram = ctk.CTkFrame(ram_panel, fg_color="transparent")
        hdr_ram.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        hdr_ram.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr_ram,
            text="Alocação de Memória Java (JVM) & Parâmetros",
            font=font_heading(14, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=0, column=0, sticky="w")

        sys_ram_gb = round(self.process_mgr.system_total_ram_mb / 1024, 1)
        ctk.CTkLabel(
            hdr_ram,
            text=f"RAM Física Total: {sys_ram_gb} GB",
            font=font_mono(11),
            text_color=PALETTE["text_secondary"],
        ).grid(row=0, column=1, sticky="e")

        # Slider Xms (Memória Inicial)
        max_slider_mb = max(4096, min(32768, int((self.process_mgr.system_total_ram_mb // 1024) * 1024)))
        cur_xms = int(self.config.get("xms_mb", 2048))
        cur_xmx = int(self.config.get("xmx_mb", 4096))

        xms_row = ctk.CTkFrame(ram_panel, fg_color="transparent")
        xms_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(6, 2))
        xms_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            xms_row,
            text="Memória Inicial (-Xms):",
            font=font_body(12),
            text_color=PALETTE["text_secondary"],
        ).grid(row=0, column=0, sticky="w")

        self.lbl_xms_val = ctk.CTkLabel(
            xms_row,
            text=f"{cur_xms} MB ({cur_xms / 1024:.1f} GB)",
            font=font_mono(12, bold=True),
            text_color=PALETTE["text_primary"],
        )
        self.lbl_xms_val.grid(row=0, column=2, sticky="e")

        self.slider_xms = ctk.CTkSlider(
            ram_panel,
            from_=512,
            to=max_slider_mb,
            number_of_steps=max(1, (max_slider_mb - 512) // 512),
            command=self._on_xms_slide,
            button_color=PALETTE["lapis"],
            button_hover_color=PALETTE["lapis_hover"],
            progress_color=PALETTE["lapis"],
        )
        self.slider_xms.set(cur_xms)
        self.slider_xms.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))

        # Slider Xmx (Memória Máxima)
        xmx_row = ctk.CTkFrame(ram_panel, fg_color="transparent")
        xmx_row.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 2))
        xmx_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            xmx_row,
            text="Memória Máxima (-Xmx):",
            font=font_body(12),
            text_color=PALETTE["text_secondary"],
        ).grid(row=0, column=0, sticky="w")

        self.lbl_xmx_val = ctk.CTkLabel(
            xmx_row,
            text=f"{cur_xmx} MB ({cur_xmx / 1024:.1f} GB)",
            font=font_mono(12, bold=True),
            text_color=PALETTE["copper"],
        )
        self.lbl_xmx_val.grid(row=0, column=2, sticky="e")

        self.slider_xmx = ctk.CTkSlider(
            ram_panel,
            from_=1024,
            to=max_slider_mb,
            number_of_steps=max(1, (max_slider_mb - 1024) // 512),
            command=self._on_xmx_slide,
            button_color=PALETTE["copper"],
            button_hover_color=PALETTE["copper_hover"],
            progress_color=PALETTE["copper"],
        )
        self.slider_xmx.set(cur_xmx)
        self.slider_xmx.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 10))

        # Flags G1GC otimizadas
        self.var_g1gc = ctk.BooleanVar(value=bool(self.config.get("use_extra_jvm_args", False)))
        self.chk_g1gc = ctk.CTkCheckBox(
            ram_panel,
            text="Incluir flags de otimização de Garbage Collector (G1GC) para reduzir travamentos de tick",
            variable=self.var_g1gc,
            command=self._update_cmd_preview,
            font=font_small(12),
            text_color=PALETTE["text_secondary"],
            fg_color=PALETTE["emerald"],
            hover_color=PALETTE["emerald_hover"],
            checkbox_width=18,
            checkbox_height=18,
        )
        self.chk_g1gc.grid(row=5, column=0, sticky="w", padx=16, pady=(0, 8))

        # Linha de comando resultante
        self.lbl_cmd_preview = ctk.CTkLabel(
            ram_panel,
            text="",
            font=font_mono(11),
            text_color=PALETTE["text_secondary"],
            fg_color=PALETTE["bg_console"],
            corner_radius=4,
            anchor="w",
            padx=10,
            pady=6,
        )
        self.lbl_cmd_preview.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 10))

        btn_bar = ctk.CTkFrame(ram_panel, fg_color="transparent")
        btn_bar.grid(row=7, column=0, sticky="ew", padx=16, pady=(0, 14))

        ctk.CTkButton(
            btn_bar,
            text="Salvar Configuração de Memória",
            command=self._save_ram_settings,
            font=font_body(12, bold=True),
            fg_color=PALETTE["emerald"],
            hover_color=PALETTE["emerald_hover"],
            text_color=PALETTE["text_inverse"],
            height=32,
            corner_radius=5,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_bar,
            text="Atualizar iniciar.bat",
            command=self._sync_bat_file,
            font=font_body(12),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["border_focus"],
            text_color=PALETTE["text_primary"],
            height=32,
            corner_radius=5,
        ).pack(side="left")

        # --- Painel Direito: Ações Rápidas do Mundo & Eventos Recentes ---
        right_panel = ctk.CTkFrame(
            bottom,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        right_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right_panel.grid_columnconfigure(0, weight=1)
        right_panel.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            right_panel,
            text="Ações Rápidas no Mundo & Registro de Eventos",
            font=font_heading(14, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 8))

        quick_grid = ctk.CTkFrame(right_panel, fg_color="transparent")
        quick_grid.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        for c in range(4):
            quick_grid.grid_columnconfigure(c, weight=1)

        quick_actions = [
            ("Salvar Mundo", "save-all"),
            ("Definir Dia", "time set day"),
            ("Definir Noite", "time set night"),
            ("Limpar Clima", "weather clear"),
        ]
        for idx, (label, cmd) in enumerate(quick_actions):
            ctk.CTkButton(
                quick_grid,
                text=label,
                command=lambda c=cmd, l=label: self._run_quick_cmd(c, l),
                font=font_small(11, bold=True),
                fg_color=PALETTE["bg_elevated"],
                hover_color=PALETTE["border_focus"],
                text_color=PALETTE["text_primary"],
                height=30,
                corner_radius=5,
            ).grid(row=0, column=idx, sticky="ew", padx=2)

        ctk.CTkLabel(
            right_panel,
            text="Últimas ocorrências registradas:",
            font=font_small(11),
            text_color=PALETTE["text_muted"],
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(2, 4))

        self.events_box = ctk.CTkTextbox(
            right_panel,
            height=135,
            fg_color=PALETTE["bg_console"],
            text_color=PALETTE["text_secondary"],
            font=font_mono(11),
            border_width=1,
            border_color=PALETTE["border_subtle"],
            corner_radius=4,
            activate_scrollbars=True,
        )
        self.events_box.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 14))
        self.events_box.configure(state="disabled")

        self._update_cmd_preview()
        self.refresh_events_feed()

    def _on_xms_slide(self, val: float) -> None:
        mb = int(round(val / 256) * 256)
        xmx = int(self.slider_xmx.get())
        if mb > xmx:
            self.slider_xmx.set(mb)
            self.lbl_xmx_val.configure(text=f"{mb} MB ({mb / 1024:.1f} GB)")
        self.lbl_xms_val.configure(text=f"{mb} MB ({mb / 1024:.1f} GB)")
        self._update_cmd_preview()

    def _on_xmx_slide(self, val: float) -> None:
        mb = int(round(val / 256) * 256)
        xms = int(self.slider_xms.get())
        if mb < xms:
            self.slider_xms.set(mb)
            self.lbl_xms_val.configure(text=f"{mb} MB ({mb / 1024:.1f} GB)")
        self.lbl_xmx_val.configure(text=f"{mb} MB ({mb / 1024:.1f} GB)")
        self._update_cmd_preview()

    def _update_cmd_preview(self) -> None:
        xms = int(round(self.slider_xms.get() / 256) * 256)
        xmx = int(round(self.slider_xmx.get() / 256) * 256)
        jar = self.config.get("jar_file", "server.jar")
        g1 = " -XX:+UseG1GC" if self.var_g1gc.get() else ""
        self.lbl_cmd_preview.configure(text=f"java -Xms{xms}M -Xmx{xmx}M{g1} -jar {jar} nogui")

    def _save_ram_settings(self) -> None:
        xms = int(round(self.slider_xms.get() / 256) * 256)
        xmx = int(round(self.slider_xmx.get() / 256) * 256)
        self.config.set("xms_mb", xms, auto_save=False)
        self.config.set("xmx_mb", xmx, auto_save=False)
        self.config.set("use_extra_jvm_args", bool(self.var_g1gc.get()), auto_save=True)
        self.chart_ram.max_value = float(xmx)
        msg = f"Memória configurada para -Xms{xms}M / -Xmx{xmx}M."
        if self.process_mgr.is_running():
            msg += " Reinicie o servidor para aplicar ao processo Java."
        self.notify_cb(msg, "success")

    def _sync_bat_file(self) -> None:
        self._save_ram_settings()
        if self.config.sync_iniciar_bat():
            self.notify_cb("Arquivo iniciar.bat atualizado com a nova alocação de memória.", "info")
        else:
            self.notify_cb("Não foi possível atualizar o iniciar.bat.", "error")

    def _run_quick_cmd(self, cmd: str, label: str) -> None:
        if not self.process_mgr.is_running():
            self.notify_cb("Inicie o servidor antes de enviar comandos ao mundo.", "warning")
            return
        if self.process_mgr.send_command(cmd):
            self.notify_cb(f"Comando '{cmd}' ({label}) enviado ao servidor.", "info")

    def refresh_static_info(self) -> None:
        self.props_mgr.load()
        port = self.props_mgr.values.get("server-port", "25565")
        world = self.props_mgr.values.get("level-name", "world")
        ver = self.process_mgr.server_version
        self.tile_status.update_metric(
            value=self.process_mgr.state,
            subtext=f"Minecraft {ver} · Porta {port} · Mundo '{world}'",
        )

    def refresh_events_feed(self) -> None:
        events = self.config.get("events", [])[:15]
        self.events_box.configure(state="normal")
        self.events_box.delete("1.0", "end")
        if not events:
            self.events_box.insert("end", "Nenhum evento registrado ainda.\n")
        else:
            for ev in events:
                ts = ev.get("timestamp", "")
                cat = ev.get("category", "Info")
                msg = ev.get("message", "")
                self.events_box.insert("end", f"[{ts}] {cat}: {msg}\n")
        self.events_box.configure(state="disabled")

    def update_live_telemetry(self) -> None:
        state = self.process_mgr.state
        color_map = {
            ServerState.ONLINE: PALETTE["emerald"],
            ServerState.STARTING: PALETTE["copper"],
            ServerState.STOPPING: PALETTE["copper"],
            ServerState.CRASHED: PALETTE["redstone"],
            ServerState.OFFLINE: PALETTE["text_muted"],
        }
        port = self.props_mgr.values.get("server-port", "25565")
        world = self.props_mgr.values.get("level-name", "world")
        self.tile_status.update_metric(
            value=state,
            subtext=f"MC {self.process_mgr.server_version} · :{port} · {world}",
            accent_color=color_map.get(state, PALETTE["text_muted"]),
        )

        # Jogadores
        max_p = self.props_mgr.values.get("max-players", "20")
        online_list = list(self.process_mgr.online_players.keys())
        p_sub = ", ".join(online_list[:3]) if online_list else "Nenhum jogador ativo"
        self.tile_players.update_metric(
            value=f"{len(online_list)} / {max_p}",
            subtext=p_sub,
            accent_color=PALETTE["emerald"] if online_list else PALETTE["lapis"],
        )

        # Uptime
        uptime_str = self.process_mgr.get_uptime_formatted()
        pid_str = f"PID {self.process_mgr.process.pid}" if self.process_mgr.is_running() and self.process_mgr.process else "Processo parado"
        self.tile_uptime.update_metric(
            value=uptime_str,
            subtext=pid_str,
        )

        # Recursos CPU / RAM
        cpu = self.process_mgr.current_cpu_percent
        ram_mb = self.process_mgr.current_ram_mb
        xmx_mb = float(self.config.get("xmx_mb", 4096))
        sys_cpu = self.process_mgr.system_cpu_percent
        sys_ram = self.process_mgr.system_ram_percent

        self.tile_resources.update_metric(
            value=f"{cpu:.1f}% · {int(ram_mb)} MB",
            subtext=f"Sistema Windows: CPU {sys_cpu:.0f}% · RAM {sys_ram:.0f}%",
            accent_color=PALETTE["redstone"] if ram_mb > xmx_mb * 0.9 else PALETTE["copper"],
        )

        # Atualizar gráficos
        self.chart_cpu.redraw(
            self.process_mgr.cpu_history,
            max_value=100.0,
            subtitle=f"Java: {cpu:.1f}%  ·  Sistema: {sys_cpu:.1f}%  ·  Pico: {max(self.process_mgr.cpu_history):.1f}%",
        )
        self.chart_ram.redraw(
            self.process_mgr.ram_history,
            max_value=xmx_mb,
            subtitle=f"Uso RSS: {int(ram_mb)} MB / {int(xmx_mb)} MB ({(ram_mb / max(1.0, xmx_mb)) * 100:.0f}%)",
        )
