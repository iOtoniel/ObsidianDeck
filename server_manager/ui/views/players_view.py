"""
Gerenciamento de Jogadores, Whitelist, Operadores (OP), Banimentos,
Mensagens Globais e Histórico de Sessões.
"""

from __future__ import annotations
from typing import Callable
import customtkinter as ctk

from ...player_manager import PlayerManager
from ...process_manager import ServerProcessManager
from ...theme import PALETTE, font_body, font_heading, font_mono, font_small


class PlayersView(ctk.CTkScrollableFrame):
    """Painel de controle de jogadores online, histórico (usercache), whitelist, OP e bans."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        player_mgr: PlayerManager,
        process_mgr: ServerProcessManager,
        notify_cb: Callable[[str, str], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.player_mgr = player_mgr
        self.process_mgr = process_mgr
        self.notify_cb = notify_cb

        self.grid_columnconfigure(0, weight=1)

        self._build_broadcast_bar()
        self._build_quick_action_bar()
        self._build_players_directory()
        self._build_lists_grid()
        self.refresh_all()

    def _build_broadcast_bar(self) -> None:
        box = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        box.grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 8))
        box.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            box,
            text="Anúncio Global:",
            font=font_heading(13, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=0, column=0, padx=(14, 10), pady=12, sticky="w")

        self.ent_broadcast = ctk.CTkEntry(
            box,
            placeholder_text="Enviar mensagem global para todos os jogadores no servidor (/say + alerta na tela)...",
            height=32,
            font=font_body(12),
            fg_color=PALETTE["bg_console"],
            border_color=PALETTE["border_default"],
        )
        self.ent_broadcast.grid(row=0, column=1, sticky="ew", padx=6, pady=12)
        self.ent_broadcast.bind("<Return>", lambda _e: self._send_broadcast())

        self.var_title_bar = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            box,
            text="Exibir na Actionbar",
            variable=self.var_title_bar,
            font=font_small(11),
            checkbox_width=16,
            checkbox_height=16,
            fg_color=PALETTE["lapis"],
        ).grid(row=0, column=2, padx=8)

        ctk.CTkButton(
            box,
            text="Transmitir Mensagem",
            command=self._send_broadcast,
            font=font_body(12, bold=True),
            fg_color=PALETTE["lapis"],
            hover_color=PALETTE["lapis_hover"],
            height=32,
            width=155,
            corner_radius=5,
        ).grid(row=0, column=3, padx=(4, 14), pady=12)

    def _build_quick_action_bar(self) -> None:
        bar = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        bar.grid(row=1, column=0, sticky="ew", padx=4, pady=(0, 10))
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            bar,
            text="Ação Manual por Nick:",
            font=font_heading(13, bold=True),
            text_color=PALETTE["text_primary"],
        ).grid(row=0, column=0, padx=(14, 10), pady=12, sticky="w")

        self.ent_target_nick = ctk.CTkEntry(
            bar,
            placeholder_text="Nome do jogador (ex: iTonyTony, cintiasz)",
            height=32,
            font=font_mono(12),
            fg_color=PALETTE["bg_console"],
            border_color=PALETTE["border_default"],
        )
        self.ent_target_nick.grid(row=0, column=1, sticky="ew", padx=4, pady=12)

        self.ent_reason = ctk.CTkEntry(
            bar,
            placeholder_text="Motivo opcional (para Kick / Ban)",
            height=32,
            font=font_body(12),
            fg_color=PALETTE["bg_console"],
            border_color=PALETTE["border_default"],
        )
        self.ent_reason.grid(row=0, column=2, sticky="ew", padx=4, pady=12)

        btns = ctk.CTkFrame(bar, fg_color="transparent")
        btns.grid(row=0, column=3, padx=(6, 14), pady=10)

        ctk.CTkButton(
            btns,
            text="+ Whitelist",
            width=90,
            height=30,
            font=font_small(11, bold=True),
            fg_color=PALETTE["emerald"],
            hover_color=PALETTE["emerald_hover"],
            text_color=PALETTE["text_inverse"],
            command=self._manual_whitelist,
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btns,
            text="+ Dar OP",
            width=80,
            height=30,
            font=font_small(11, bold=True),
            fg_color=PALETTE["copper"],
            hover_color=PALETTE["copper_hover"],
            text_color=PALETTE["text_inverse"],
            command=self._manual_op,
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btns,
            text="Kick",
            width=64,
            height=30,
            font=font_small(11, bold=True),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["border_focus"],
            command=self._manual_kick,
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            btns,
            text="Banir",
            width=68,
            height=30,
            font=font_small(11, bold=True),
            fg_color=PALETTE["redstone"],
            hover_color=PALETTE["redstone_hover"],
            command=self._manual_ban,
        ).pack(side="left", padx=3)

    def _build_players_directory(self) -> None:
        section = ctk.CTkFrame(
            self,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        section.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 10))
        section.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(section, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(12, 6))
        hdr.grid_columnconfigure(0, weight=1)

        self.lbl_roster_title = ctk.CTkLabel(
            hdr,
            text="Diretório & Histórico de Jogadores do Servidor",
            font=font_heading(14, bold=True),
            text_color=PALETTE["text_primary"],
        )
        self.lbl_roster_title.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            hdr,
            text="Atualizar Lista",
            width=110,
            height=28,
            font=font_small(11),
            fg_color=PALETTE["bg_elevated"],
            hover_color=PALETTE["border_focus"],
            command=self.refresh_all,
        ).grid(row=0, column=1, sticky="e")

        self.roster_container = ctk.CTkFrame(section, fg_color="transparent")
        self.roster_container.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 14))
        self.roster_container.grid_columnconfigure(0, weight=1)

    def _build_lists_grid(self) -> None:
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.grid(row=3, column=0, sticky="ew", padx=4, pady=(0, 10))
        for c in range(3):
            grid.grid_columnconfigure(c, weight=1, uniform="plist")

        # Coluna 0: Whitelist
        self.wl_card = self._create_list_card(grid, 0, "Whitelist (whitelist.json)", PALETTE["emerald"])
        # Coluna 1: Operadores (OPs)
        self.op_card = self._create_list_card(grid, 1, "Operadores (ops.json)", PALETTE["copper"])
        # Coluna 2: Jogadores Banidos
        self.ban_card = self._create_list_card(grid, 2, "Banidos (banned-players.json)", PALETTE["redstone"])

    def _create_list_card(self, parent: ctk.CTkFrame, col: int, title: str, accent: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            parent,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
        )
        padx = (0, 6) if col == 0 else ((6, 6) if col == 1 else (6, 0))
        card.grid(row=0, column=col, sticky="nsew", padx=padx)
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        ctk.CTkLabel(
            top,
            text=title,
            font=font_heading(13, bold=True),
            text_color=accent,
        ).pack(side="left")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        return body

    # -----------------------------------------------------------------------
    # Atualização dinâmica dos cartões de jogadores
    # -----------------------------------------------------------------------
    def refresh_all(self) -> None:
        for w in self.roster_container.winfo_children():
            w.destroy()

        players = self.player_mgr.get_all_known_players()
        online_count = sum(1 for p in players if p["online"])
        self.lbl_roster_title.configure(
            text=f"Diretório & Histórico de Jogadores ({online_count} online · {len(players)} registrados)"
        )

        if not players:
            ctk.CTkLabel(
                self.roster_container,
                text="Nenhum jogador encontrado no usercache.json ainda.",
                font=font_body(12),
                text_color=PALETTE["text_muted"],
            ).grid(row=0, column=0, pady=12)
        else:
            for idx, p in enumerate(players):
                self._render_player_row(self.roster_container, idx, p)

        # Renderizar Whitelist
        for w in self.wl_card.winfo_children():
            w.destroy()
        wl_items = self.player_mgr.get_whitelist()
        if not wl_items:
            ctk.CTkLabel(self.wl_card, text="Whitelist vazia.", font=font_small(11), text_color=PALETTE["text_muted"]).grid(
                row=0, column=0, sticky="w", pady=4
            )
        for i, item in enumerate(wl_items):
            name = str(item.get("name", "?"))
            row = ctk.CTkFrame(self.wl_card, fg_color=PALETTE["bg_elevated"], corner_radius=4)
            row.grid(row=i, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=name, font=font_mono(12, bold=True), text_color=PALETTE["text_primary"]).grid(
                row=0, column=0, padx=10, pady=5, sticky="w"
            )
            ctk.CTkButton(
                row,
                text="Remover",
                width=68,
                height=22,
                font=font_small(10),
                fg_color=PALETTE["bg_surface"],
                hover_color=PALETTE["redstone"],
                command=lambda n=name: self._remove_wl(n),
            ).grid(row=0, column=1, padx=6, pady=4)

        # Renderizar OPs
        for w in self.op_card.winfo_children():
            w.destroy()
        op_items = self.player_mgr.get_ops()
        if not op_items:
            ctk.CTkLabel(self.op_card, text="Nenhum operador OP.", font=font_small(11), text_color=PALETTE["text_muted"]).grid(
                row=0, column=0, sticky="w", pady=4
            )
        for i, item in enumerate(op_items):
            name = str(item.get("name", "?"))
            lvl = item.get("level", 4)
            row = ctk.CTkFrame(self.op_card, fg_color=PALETTE["bg_elevated"], corner_radius=4)
            row.grid(row=i, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                row, text=f"{name} (Nível {lvl})", font=font_mono(12, bold=True), text_color=PALETTE["text_primary"]
            ).grid(row=0, column=0, padx=10, pady=5, sticky="w")
            ctk.CTkButton(
                row,
                text="Tirar OP",
                width=68,
                height=22,
                font=font_small(10),
                fg_color=PALETTE["bg_surface"],
                hover_color=PALETTE["redstone"],
                command=lambda n=name: self._remove_op(n),
            ).grid(row=0, column=1, padx=6, pady=4)

        # Renderizar Banidos
        for w in self.ban_card.winfo_children():
            w.destroy()
        ban_items = self.player_mgr.get_banned_players()
        if not ban_items:
            ctk.CTkLabel(self.ban_card, text="Nenhum jogador banido.", font=font_small(11), text_color=PALETTE["text_muted"]).grid(
                row=0, column=0, sticky="w", pady=4
            )
        for i, item in enumerate(ban_items):
            name = str(item.get("name", "?"))
            reason = str(item.get("reason", ""))
            row = ctk.CTkFrame(self.ban_card, fg_color=PALETTE["bg_elevated"], corner_radius=4)
            row.grid(row=i, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(
                row, text=f"{name} ({reason[:18]})", font=font_mono(11, bold=True), text_color=PALETTE["redstone"]
            ).grid(row=0, column=0, padx=10, pady=5, sticky="w")
            ctk.CTkButton(
                row,
                text="Desbanir",
                width=68,
                height=22,
                font=font_small(10),
                fg_color=PALETTE["emerald"],
                hover_color=PALETTE["emerald_hover"],
                text_color=PALETTE["text_inverse"],
                command=lambda n=name: self._pardon(n),
            ).grid(row=0, column=1, padx=6, pady=4)

    def _render_player_row(self, parent: ctk.CTkFrame, row_idx: int, p: dict) -> None:
        name = p["name"]
        is_online = p["online"]
        is_op = p["is_op"]
        is_wl = p["is_whitelisted"]
        is_banned = p["is_banned"]

        row = ctk.CTkFrame(
            parent,
            fg_color=PALETTE["bg_elevated"],
            corner_radius=5,
            border_width=1,
            border_color=PALETTE["emerald"] if is_online else PALETTE["border_subtle"],
        )
        row.grid(row=row_idx, column=0, sticky="ew", pady=4)
        row.grid_columnconfigure(1, weight=1)

        # Indicador de Status
        badge_color = PALETTE["emerald"] if is_online else (PALETTE["redstone"] if is_banned else PALETTE["text_muted"])
        badge_text = "● ONLINE" if is_online else ("BANIDO" if is_banned else "OFFLINE")
        ctk.CTkLabel(
            row,
            text=badge_text,
            font=font_mono(11, bold=True),
            text_color=badge_color,
            width=82,
            anchor="w",
        ).grid(row=0, column=0, padx=(12, 6), pady=10, sticky="w")

        # Nome + Metadados (UUID, IP, Sessões)
        tags = []
        if is_op:
            tags.append("[OP]")
        if is_wl:
            tags.append("[Whitelist]")
        tag_str = " ".join(tags)
        meta_text = f"{name}  {tag_str}   ·   UUID: {str(p['uuid'])[:18]}...   ·   IP: {p['last_ip']}   ·   Visto: {p['last_seen']}"

        ctk.CTkLabel(
            row,
            text=meta_text,
            font=font_mono(12, bold=is_online),
            text_color=PALETTE["text_primary"] if is_online else PALETTE["text_secondary"],
            anchor="w",
        ).grid(row=0, column=1, padx=6, pady=10, sticky="ew")

        # Botões de ação rápida por linha
        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=2, padx=(6, 10), pady=6)

        # Alternar Whitelist
        wl_txt = "Tirar WL" if is_wl else "+ Whitelist"
        ctk.CTkButton(
            actions,
            text=wl_txt,
            width=78,
            height=26,
            font=font_small(11),
            fg_color=PALETTE["bg_surface"] if is_wl else PALETTE["emerald"],
            hover_color=PALETTE["emerald_hover"],
            text_color=PALETTE["text_primary"] if is_wl else PALETTE["text_inverse"],
            command=lambda n=name, w=is_wl: self._remove_wl(n) if w else self._add_wl(n),
        ).pack(side="left", padx=2)

        # Alternar OP
        op_txt = "Tirar OP" if is_op else "+ OP"
        ctk.CTkButton(
            actions,
            text=op_txt,
            width=64,
            height=26,
            font=font_small(11),
            fg_color=PALETTE["bg_surface"] if is_op else PALETTE["copper"],
            hover_color=PALETTE["copper_hover"],
            text_color=PALETTE["text_primary"] if is_op else PALETTE["text_inverse"],
            command=lambda n=name, o=is_op: self._remove_op(n) if o else self._add_op(n),
        ).pack(side="left", padx=2)

        # Gamemode rápido (se online)
        ctk.CTkButton(
            actions,
            text="Criativo",
            width=62,
            height=26,
            font=font_small(11),
            fg_color=PALETTE["bg_surface"],
            hover_color=PALETTE["lapis"],
            command=lambda n=name: self._set_gamemode(n, "creative"),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            actions,
            text="Survival",
            width=62,
            height=26,
            font=font_small(11),
            fg_color=PALETTE["bg_surface"],
            hover_color=PALETTE["lapis"],
            command=lambda n=name: self._set_gamemode(n, "survival"),
        ).pack(side="left", padx=2)

        # Kick
        ctk.CTkButton(
            actions,
            text="Kick",
            width=52,
            height=26,
            font=font_small(11),
            fg_color=PALETTE["bg_surface"],
            hover_color=PALETTE["copper"],
            command=lambda n=name: self._kick(n),
        ).pack(side="left", padx=2)

        # Ban / Pardon
        if is_banned:
            ctk.CTkButton(
                actions,
                text="Desbanir",
                width=68,
                height=26,
                font=font_small(11, bold=True),
                fg_color=PALETTE["emerald"],
                hover_color=PALETTE["emerald_hover"],
                text_color=PALETTE["text_inverse"],
                command=lambda n=name: self._pardon(n),
            ).pack(side="left", padx=2)
        else:
            ctk.CTkButton(
                actions,
                text="Banir",
                width=56,
                height=26,
                font=font_small(11, bold=True),
                fg_color=PALETTE["redstone"],
                hover_color=PALETTE["redstone_hover"],
                command=lambda n=name: self._ban(n),
            ).pack(side="left", padx=2)

    # -----------------------------------------------------------------------
    # Handlers
    # -----------------------------------------------------------------------
    def _send_broadcast(self) -> None:
        msg = self.ent_broadcast.get().strip()
        ok, res = self.player_mgr.broadcast_message(msg, use_title=self.var_title_bar.get())
        if ok:
            self.ent_broadcast.delete(0, "end")
        self.notify_cb(res, "success" if ok else "warning")

    def _manual_whitelist(self) -> None:
        nick = self.ent_target_nick.get().strip()
        self._add_wl(nick)

    def _manual_op(self) -> None:
        nick = self.ent_target_nick.get().strip()
        self._add_op(nick)

    def _manual_kick(self) -> None:
        nick = self.ent_target_nick.get().strip()
        reason = self.ent_reason.get().strip() or "Expulso pelo administrador"
        if not nick:
            self.notify_cb("Informe o nick do jogador.", "warning")
            return
        ok, msg = self.player_mgr.kick_player(nick, reason)
        self.notify_cb(msg, "info" if ok else "warning")

    def _manual_ban(self) -> None:
        nick = self.ent_target_nick.get().strip()
        reason = self.ent_reason.get().strip() or "Banido pelo administrador"
        if not nick:
            self.notify_cb("Informe o nick do jogador.", "warning")
            return
        ok, msg = self.player_mgr.ban_player(nick, reason)
        self.refresh_all()
        self.notify_cb(msg, "error" if ok else "warning")

    def _add_wl(self, name: str) -> None:
        ok, msg = self.player_mgr.add_whitelist(name)
        self.refresh_all()
        self.notify_cb(msg, "success" if ok else "warning")

    def _remove_wl(self, name: str) -> None:
        ok, msg = self.player_mgr.remove_whitelist(name)
        self.refresh_all()
        self.notify_cb(msg, "info" if ok else "warning")

    def _add_op(self, name: str) -> None:
        ok, msg = self.player_mgr.add_op(name)
        self.refresh_all()
        self.notify_cb(msg, "success" if ok else "warning")

    def _remove_op(self, name: str) -> None:
        ok, msg = self.player_mgr.remove_op(name)
        self.refresh_all()
        self.notify_cb(msg, "info" if ok else "warning")

    def _kick(self, name: str) -> None:
        reason = self.ent_reason.get().strip() or "Expulso pelo painel"
        ok, msg = self.player_mgr.kick_player(name, reason)
        self.notify_cb(msg, "warning")

    def _ban(self, name: str) -> None:
        reason = self.ent_reason.get().strip() or "Banido pelo painel"
        ok, msg = self.player_mgr.ban_player(name, reason)
        self.refresh_all()
        self.notify_cb(msg, "error")

    def _pardon(self, name: str) -> None:
        ok, msg = self.player_mgr.pardon_player(name)
        self.refresh_all()
        self.notify_cb(msg, "success" if ok else "warning")

    def _set_gamemode(self, name: str, mode: str) -> None:
        if not self.process_mgr.is_running():
            self.notify_cb("O servidor precisa estar online para alterar o modo de jogo de um jogador.", "warning")
            return
        self.process_mgr.send_command(f"gamemode {mode} {name}")
        self.notify_cb(f"Modo de jogo de {name} alterado para {mode}.", "info")
