"""
Componentes visuais customizados de baixo consumo de recursos:
- TelemetryOscilloscope: Gráfico em tempo real em tk.Canvas para CPU (%) e RAM (MB)
- MetricBlock: Bloco estrutural de telemetria sem clichês de cartões genéricos
- SectionHeader: Cabeçalho tipográfico intencional
"""

from __future__ import annotations
import tkinter as tk
from typing import Sequence
import customtkinter as ctk

from ..theme import PALETTE, font_body, font_display, font_heading, font_mono, font_small


class TelemetryOscilloscope(ctk.CTkFrame):
    """
    Gráfico em tempo real de canal duplo ou único desenhado diretamente em tk.Canvas.
    Consumo de memória e CPU próximo de zero (sem peso do Matplotlib).
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        title: str,
        unit: str = "%",
        line_color: str = PALETTE["emerald"],
        fill_color: str = "#11281E",
        max_value: float = 100.0,
        height: int = 165,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
            **kwargs,
        )
        self.title_text = title
        self.unit = unit
        self.line_color = line_color
        self.fill_color = fill_color
        self.max_value = max(1.0, max_value)
        self.canvas_height = height
        self._last_values: Sequence[float] = [0.0] * 60

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Barra de topo do gráfico
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        header.grid_columnconfigure(0, weight=1)

        self.lbl_title = ctk.CTkLabel(
            header,
            text=title,
            font=font_heading(13, bold=True),
            text_color=PALETTE["text_primary"],
            anchor="w",
        )
        self.lbl_title.grid(row=0, column=0, sticky="w")

        self.lbl_stats = ctk.CTkLabel(
            header,
            text=f"Atual: 0.0 {unit}   Pico: 0.0 {unit}",
            font=font_mono(12, bold=True),
            text_color=line_color,
            anchor="e",
        )
        self.lbl_stats.grid(row=0, column=1, sticky="e")

        # Canvas nativo acelerado
        self.canvas = tk.Canvas(
            self,
            bg=PALETTE["bg_console"],
            height=self.canvas_height,
            highlightthickness=1,
            highlightbackground=PALETTE["border_subtle"],
            bd=0,
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=12, pady=(2, 12))
        self.canvas.bind("<Configure>", lambda _e: self.redraw(self._last_values, self.max_value))

    def redraw(self, values: Sequence[float], max_value: float | None = None, subtitle: str = "") -> None:
        self._last_values = list(values) if values else [0.0]
        if max_value is not None and max_value > 0:
            self.max_value = float(max_value)

        c = self.canvas
        w = max(100, c.winfo_width())
        h = max(60, c.winfo_height())
        c.delete("all")

        pad_left = 42
        pad_right = 10
        pad_top = 12
        pad_bottom = 18
        plot_w = max(20, w - pad_left - pad_right)
        plot_h = max(20, h - pad_top - pad_bottom)

        # Linhas horizontais de referência (0%, 25%, 50%, 75%, 100%)
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = pad_top + plot_h * (1.0 - frac)
            c.create_line(
                pad_left,
                y,
                w - pad_right,
                y,
                fill="#19202B" if frac not in (0.0, 1.0) else "#222B3A",
                dash=(2, 4) if frac not in (0.0, 1.0) else (),
            )
            label_val = self.max_value * frac
            if self.unit == "%":
                lbl_str = f"{int(label_val)}%"
            elif label_val >= 1024:
                lbl_str = f"{label_val / 1024:.1f}G"
            else:
                lbl_str = f"{int(label_val)}M"
            c.create_text(
                pad_left - 6,
                y,
                text=lbl_str,
                fill=PALETTE["text_muted"],
                font=("Consolas", 8),
                anchor="e",
            )

        # Grades verticais de tempo (60s -> a cada 15s)
        for idx, sec_lbl in enumerate(("-60s", "-45s", "-30s", "-15s", "Agora")):
            x = pad_left + (plot_w * idx / 4.0)
            c.create_line(x, pad_top, x, pad_top + plot_h, fill="#151B24")
            c.create_text(
                x,
                h - 4,
                text=sec_lbl,
                fill=PALETTE["text_muted"],
                font=("Consolas", 8),
                anchor="s",
            )

        pts = list(self._last_values)
        n = len(pts)
        if n < 2:
            pts = [0.0, 0.0]
            n = 2

        coords = []
        for i, val in enumerate(pts):
            x = pad_left + (i / (n - 1)) * plot_w
            clamped = max(0.0, min(self.max_value, float(val)))
            y = pad_top + plot_h * (1.0 - (clamped / self.max_value))
            coords.append((x, y))

        # Polígono de área preenchida
        poly_pts = [pad_left, pad_top + plot_h]
        for x, y in coords:
            poly_pts.extend([x, y])
        poly_pts.extend([coords[-1][0], pad_top + plot_h])
        c.create_polygon(poly_pts, fill=self.fill_color, outline="")

        # Linha principal
        line_pts = []
        for x, y in coords:
            line_pts.extend([x, y])
        c.create_line(line_pts, fill=self.line_color, width=2, smooth=False)

        # Ponto indicador na leitura mais recente
        last_x, last_y = coords[-1]
        c.create_oval(
            last_x - 3.5,
            last_y - 3.5,
            last_x + 3.5,
            last_y + 3.5,
            fill=self.line_color,
            outline=PALETTE["bg_console"],
            width=1,
        )

        cur_val = pts[-1] if pts else 0.0
        peak_val = max(pts) if pts else 0.0
        if subtitle:
            self.lbl_stats.configure(text=subtitle)
        else:
            self.lbl_stats.configure(
                text=f"Atual: {cur_val:.1f} {self.unit}   ·   Pico (60s): {peak_val:.1f} {self.unit}"
            )


class MetricTile(ctk.CTkFrame):
    """Bloco de leitura direta com barra de acento lateral fina e tipografia clara."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        label: str,
        value: str,
        subtext: str = "",
        accent_color: str = PALETTE["emerald"],
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color=PALETTE["bg_surface"],
            corner_radius=6,
            border_width=1,
            border_color=PALETTE["border_subtle"],
            **kwargs,
        )
        self.grid_columnconfigure(1, weight=1)

        self.accent_bar = ctk.CTkFrame(
            self,
            width=4,
            fg_color=accent_color,
            corner_radius=2,
        )
        self.accent_bar.grid(row=0, column=0, rowspan=3, sticky="ns", padx=(10, 10), pady=12)

        self.lbl_label = ctk.CTkLabel(
            self,
            text=label,
            font=font_small(12, bold=False),
            text_color=PALETTE["text_secondary"],
            anchor="w",
        )
        self.lbl_label.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(10, 0))

        self.lbl_value = ctk.CTkLabel(
            self,
            text=value,
            font=font_mono(19, bold=True),
            text_color=PALETTE["text_primary"],
            anchor="w",
        )
        self.lbl_value.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(1, 1))

        self.lbl_sub = ctk.CTkLabel(
            self,
            text=subtext,
            font=font_small(11),
            text_color=PALETTE["text_muted"],
            anchor="w",
        )
        self.lbl_sub.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=(0, 10))

    def update_metric(
        self,
        value: str,
        subtext: str | None = None,
        accent_color: str | None = None,
    ) -> None:
        self.lbl_value.configure(text=value)
        if subtext is not None:
            self.lbl_sub.configure(text=subtext)
        if accent_color is not None:
            self.accent_bar.configure(fg_color=accent_color)
