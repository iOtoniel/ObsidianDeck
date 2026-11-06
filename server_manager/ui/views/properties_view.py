"""
Editor Visual do `server.properties` com validação em tempo real,
filtros por categoria e indicação clara de alterações que exigem reinicialização.
"""

from __future__ import annotations
from typing import Callable, Dict, Tuple
import customtkinter as ctk

from ...process_manager import ServerProcessManager
from ...properties_manager import PROPERTY_SPECS, PropertySpec, ServerPropertiesManager
from ...theme import PALETTE, font_body, font_heading, font_mono, font_small


class PropertiesView(ctk.CTkFrame):
    """Interface visual estruturada para editar e validar server.properties."""

    CATEGORIES = [
        "Principais",
        "Geral & Rede",
        "Jogabilidade & Mundo",
        "Performance & Chunks",
        "Segurança & Acesso",
        "Todas (Avançado)",
    ]

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        props_mgr: ServerPropertiesManager,
        process_mgr: ServerProcessManager,
        notify_cb: Callable[[str, str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.props_mgr = props_mgr
        self.process_mgr = process_mgr
        self.notify_cb = notify_cb

        self.current_category = "Principais"
        self.search_term = ""
        # Mapeia chave -> (tipo_widget, getter_callable, row_frame)
        self.field_getters: Dict[str, Callable[[], str]] = {}
        self.draft_values: Dict[str, str] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_top_bar()
        self._build_restart_banner()
        self._build_scroll_form()
        self.reload_from_disk()

    def _build_top_bar(self) -> None:
        bar = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        bar.grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 8))
        bar.grid_columnconfigure(1, weight=1)

        self.seg_cat = ctk.CTkSegmentedButton(
            bar,
            values=self.CATEGORIES,
            command=self._on_category_change,
            font=font_small(11, bold=True),
            selected_color=PALETTE["lapis"],
            selected_hover_color=PALETTE["lapis_hover"],
            unselected_color=PALETTE["bg_elevated"],
        )
        self.seg_cat.set("Principais")
        self.seg_cat.grid(row=0, column=0, padx=12, pady=10, sticky="w")

        self.ent_search = ctk.CTkEntry(
            bar,
            placeholder_text="Buscar propriedade (ex: motd, port, distance)...",
            width=220,
            height=30,
            font=font_small(11),
            fg_color=PALETTE["bg_console"],
            border_color=PALETTE["border_default"],
        )
        self.ent_search.grid(row=0, column=1, padx=6, pady=10, sticky="e")
        self.ent_search.bind("<KeyRelease>", self._on_search_change)

        ctk.CTkButton(
            bar,
            text="Recarregar",
            width=88,
            height=30,
            font=font_small(11),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["border_focus"],
            command=self.reload_from_disk,
        ).grid(row=0, column=2, padx=4, pady=10)

        ctk.CTkButton(
            bar,
            text="Salvar Alterações",
            width=135,
            height=30,
            font=font_body(12, bold=True),
            fg_color=PALETTE["emerald"],
            hover_color=PALETTE["emerald_hover"],
            text_color=PALETTE["text_inverse"],
            command=self._save_changes,
        ).grid(row=0, column=3, padx=(4, 12), pady=10)

    def _build_restart_banner(self) -> None:
        self.banner_frame = ctk.CTkFrame(
            self,
            fg_color=PALETTE["copper_dim"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["copper"],
        )
        self.banner_frame.grid_columnconfigure(0, weight=1)

        self.lbl_banner = ctk.CTkLabel(
            self.banner_frame,
            text="⚠ Alterações em propriedades estruturais detectadas. O servidor precisará ser reiniciado para aplicá-las.",
            font=font_body(12, bold=True),
            text_color=PALETTE["copper"],
            anchor="w",
        )
        self.lbl_banner.grid(row=0, column=0, padx=14, pady=8, sticky="ew")

        ctk.CTkButton(
            self.banner_frame,
            text="Salvar e Reiniciar Servidor Agora",
            height=28,
            font=font_small(11, bold=True),
            fg_color=PALETTE["copper"],
            hover_color=PALETTE["copper_hover"],
            text_color=PALETTE["text_inverse"],
            command=self._save_and_restart,
        ).grid(row=0, column=1, padx=12, pady=6)

    def _build_scroll_form(self) -> None:
        self.scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        self.scroll.grid(row=2, column=0, sticky="nsew", padx=4, pady=(0, 4))
        self.scroll.grid_columnconfigure(0, weight=1)

    def _sync_current_widgets_to_draft(self) -> None:
        for k, getter in self.field_getters.items():
            try:
                self.draft_values[k] = getter()
            except Exception:
                pass

    def reload_from_disk(self) -> None:
        self.props_mgr.load()
        self.draft_values = dict(self.props_mgr.values)
        self._render_fields()
        self._check_dirty_banner()

    def _on_category_change(self, val: str) -> None:
        self._sync_current_widgets_to_draft()
        self.current_category = val
        self._render_fields()

    def _on_search_change(self, _event=None) -> None:
        self._sync_current_widgets_to_draft()
        self.search_term = self.ent_search.get().strip().lower()
        self._render_fields()

    def _render_fields(self) -> None:
        for w in self.scroll.winfo_children():
            w.destroy()
        self.field_getters.clear()

        keys_to_show = []
        if self.current_category == "Principais":
            keys_to_show = list(PROPERTY_SPECS.keys())
        elif self.current_category == "Todas (Avançado)":
            keys_to_show = sorted(self.draft_values.keys())
        else:
            keys_to_show = [
                k for k, spec in PROPERTY_SPECS.items() if spec.category == self.current_category
            ]

        if self.search_term:
            # Quando há busca, pesquisa em todas as chaves do arquivo
            all_k = list(dict.fromkeys(list(PROPERTY_SPECS.keys()) + sorted(self.draft_values.keys())))
            filtered = []
            for k in all_k:
                spec = PROPERTY_SPECS.get(k)
                haystack = f"{k} {spec.label if spec else ''} {spec.description if spec else ''}".lower()
                if self.search_term in haystack:
                    filtered.append(k)
            keys_to_show = filtered

        if not keys_to_show:
            ctk.CTkLabel(
                self.scroll,
                text="Nenhuma propriedade encontrada para o filtro atual.",
                font=font_body(12),
                text_color=PALETTE["text_muted"],
            ).grid(row=0, column=0, pady=24)
            return

        for idx, key in enumerate(keys_to_show):
            val = self.draft_values.get(key, "")
            spec = PROPERTY_SPECS.get(key)
            self._create_property_row(idx, key, val, spec)

    def _create_property_row(
        self,
        row_idx: int,
        key: str,
        val: str,
        spec: PropertySpec | None,
    ) -> None:
        card = ctk.CTkFrame(
            self.scroll,
            fg_color=PALETTE["bg_elevated"],
            corner_radius=5,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        card.grid(row=row_idx, column=0, sticky="ew", padx=8, pady=4)
        card.grid_columnconfigure(0, weight=1)

        # Coluna esquerda: Título, chave técnica e descrição
        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        info.grid_columnconfigure(0, weight=1)

        title_line = ctk.CTkFrame(info, fg_color="transparent")
        title_line.grid(row=0, column=0, sticky="w")

        title_txt = spec.label if spec else key
        ctk.CTkLabel(
            title_line,
            text=title_txt,
            font=font_heading(13, bold=True),
            text_color=PALETTE["text_primary"],
        ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(
            title_line,
            text=key,
            font=font_mono(11),
            text_color=PALETTE["lapis"],
        ).pack(side="left", padx=(0, 8))

        req_restart = spec.requires_restart if spec else True
        badge_txt = "Requer Reinício" if req_restart else "Tempo Real"
        badge_col = PALETTE["copper"] if req_restart else PALETTE["emerald"]
        ctk.CTkLabel(
            title_line,
            text=f"[{badge_txt}]",
            font=font_mono(10, bold=True),
            text_color=badge_col,
        ).pack(side="left")

        desc_txt = spec.description if spec else "Parâmetro nativo do arquivo server.properties."
        ctk.CTkLabel(
            info,
            text=desc_txt,
            font=font_small(11),
            text_color=PALETTE["text_secondary"],
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Coluna direita: Controle de Edição
        ctrl_wrap = ctk.CTkFrame(card, fg_color="transparent")
        ctrl_wrap.grid(row=0, column=1, padx=14, pady=8, sticky="e")

        prop_type = spec.prop_type if spec else ("bool" if val.lower() in ("true", "false") else "str")

        if prop_type == "bool":
            var = ctk.BooleanVar(value=(val.lower() == "true"))
            sw = ctk.CTkSwitch(
                ctrl_wrap,
                text="Ativado" if var.get() else "Desativado",
                variable=var,
                font=font_mono(12, bold=True),
                progress_color=PALETTE["emerald"],
                button_color=PALETTE["text_primary"],
            )

            def _on_sw_toggle(v=var, s=sw, k=key) -> None:
                s.configure(text="Ativado" if v.get() else "Desativado")
                self.draft_values[k] = "true" if v.get() else "false"
                self._check_dirty_banner()

            sw.configure(command=_on_sw_toggle)
            sw.pack(side="right")
            self.field_getters[key] = lambda v=var: "true" if v.get() else "false"

        elif prop_type == "enum" and spec and spec.options:
            opts = spec.options
            cur = val if val in opts else opts[0]
            cmb = ctk.CTkOptionMenu(
                ctrl_wrap,
                values=opts,
                width=165,
                height=30,
                font=font_mono(12),
                fg_color=PALETTE["bg_surface"],
                button_color=PALETTE["lapis"],
                button_hover_color=PALETTE["lapis_hover"],
                command=lambda choice, k=key: self._on_field_edit(k, choice),
            )
            cmb.set(cur)
            cmb.pack(side="right")
            self.field_getters[key] = cmb.get

        else:
            ent = ctk.CTkEntry(
                ctrl_wrap,
                width=230 if key == "motd" else 165,
                height=30,
                font=font_mono(12),
                fg_color=PALETTE["bg_console"],
                border_color=PALETTE["border_default"],
            )
            ent.insert(0, val)
            ent.bind("<KeyRelease>", lambda _e, k=key, e=ent: self._on_entry_key(k, e))
            ent.pack(side="right")
            self.field_getters[key] = lambda e=ent: e.get().strip()

    def _on_field_edit(self, key: str, value: str) -> None:
        self.draft_values[key] = value
        self._check_dirty_banner()

    def _on_entry_key(self, key: str, entry_widget: ctk.CTkEntry) -> None:
        val = entry_widget.get().strip()
        ok, _err = self.props_mgr.validate_property(key, val)
        entry_widget.configure(border_color=PALETTE["border_default"] if ok else PALETTE["redstone"])
        self.draft_values[key] = val
        self._check_dirty_banner()

    def _check_dirty_banner(self) -> None:
        restart_keys = self.props_mgr.get_restart_required_changes(self.draft_values)
        if restart_keys:
            preview = ", ".join(restart_keys[:4])
            if len(restart_keys) > 4:
                preview += f" (+{len(restart_keys) - 4})"
            self.lbl_banner.configure(
                text=f"⚠ Alterações que exigem reinicialização do servidor: {preview}"
            )
            self.banner_frame.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 8))
        else:
            self.banner_frame.grid_forget()

    def _save_changes(self) -> Tuple[bool, List[str]]:
        self._sync_current_widgets_to_draft()
        ok, msg, restart_keys = self.props_mgr.save(self.draft_values)
        if not ok:
            self.notify_cb(msg, "error")
            return False, []

        # Se white-list ou difficulty mudaram e o servidor está online, aplicar também via comando
        if self.process_mgr.is_running():
            wl_val = self.draft_values.get("white-list", "false").lower()
            self.process_mgr.send_command("whitelist on" if wl_val == "true" else "whitelist off", log_echo=False)
            diff_val = self.draft_values.get("difficulty")
            if diff_val:
                self.process_mgr.send_command(f"difficulty {diff_val}", log_echo=False)

        self._check_dirty_banner()
        if restart_keys and self.process_mgr.is_running():
            self.notify_cb(
                f"Salvo! Reinicie o servidor para aplicar alterações em: {', '.join(restart_keys[:3])}.",
                "warning",
            )
        else:
            self.notify_cb(msg, "success")
        return True, restart_keys

    def _save_and_restart(self) -> None:
        ok, _rk = self._save_changes()
        if ok:
            if self.process_mgr.is_running():
                self.notify_cb("Reiniciando o servidor para aplicar novas propriedades...", "warning")
                self.process_mgr.restart_server()
            else:
                self.notify_cb("Propriedades salvas. Iniciando o servidor...", "info")
                self.process_mgr.start_server()
