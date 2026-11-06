"""
Sistema de Design Tokens, Paleta Obsidian & Copper, Tipografia e Ícones Procedurais.
Desenvolvido seguindo diretrizes de design intencional: contraste mineral, hierarquia
tipográfica limpa e ausência de ornamentos genéricos.
"""

from __future__ import annotations
from typing import Dict, Tuple
from PIL import Image, ImageDraw
import customtkinter as ctk

# ---------------------------------------------------------------------------
# Paleta de Cores — Obsidian & Copper Telemetry
# ---------------------------------------------------------------------------
PALETTE: Dict[str, str] = {
    # Superfícies minerais escuras
    "bg_root": "#0C0E12",         # Obsidian profunda (fundo da janela)
    "bg_sidebar": "#101318",      # Ardósia lateral
    "bg_header": "#11151C",       # Barra de comando superior
    "bg_surface": "#151921",      # Superfície de painel primário
    "bg_elevated": "#1B202B",     # Superfície elevada / hover / inputs
    "bg_console": "#090B0E",      # Terminal de alta legibilidade
    "bg_glass": "#222938",        # Destaque sutil de seleção ativa

    # Bordas estruturais (1px nítidas)
    "border_subtle": "#1E2430",
    "border_default": "#262E3D",
    "border_focus": "#3B485E",

    # Sinais semânticos (inspirados em minérios do Minecraft, calibrados para UI)
    "emerald": "#2ECC71",         # Online / Iniciar / Sucesso
    "emerald_hover": "#25A85C",
    "emerald_dim": "#132A1F",

    "copper": "#E67E22",          # Memória / Reiniciar / Aviso
    "copper_hover": "#CA6A16",
    "copper_dim": "#2D1E12",

    "redstone": "#E74C3C",        # Parar / Erro / Banir
    "redstone_hover": "#C0392B",
    "redstone_dim": "#2D1416",

    "lapis": "#3498DB",           # Informação / Comandos / Seleção
    "lapis_hover": "#287BB5",
    "lapis_dim": "#132334",

    "amethyst": "#9B59B6",        # Automação / Backups agendados

    # Tipografia
    "text_primary": "#EDF2F7",    # Quartzo claro
    "text_secondary": "#94A3B8",  # Cinza ardósia médio
    "text_muted": "#64748B",      # Metadados e dicas
    "text_inverse": "#090B0E",
}


# ---------------------------------------------------------------------------
# Escala Tipográfica
# ---------------------------------------------------------------------------
UI_FONT_FAMILY = "Segoe UI"
MONO_FONT_FAMILY = "Consolas"


def font_display(size: int = 20, bold: bool = True) -> ctk.CTkFont:
    return ctk.CTkFont(family=UI_FONT_FAMILY, size=size, weight="bold" if bold else "normal")


def font_heading(size: int = 15, bold: bool = True) -> ctk.CTkFont:
    return ctk.CTkFont(family=UI_FONT_FAMILY, size=size, weight="bold" if bold else "normal")


def font_body(size: int = 13, bold: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=UI_FONT_FAMILY, size=size, weight="bold" if bold else "normal")


def font_small(size: int = 11, bold: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=UI_FONT_FAMILY, size=size, weight="bold" if bold else "normal")


def font_mono(size: int = 12, bold: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(family=MONO_FONT_FAMILY, size=size, weight="bold" if bold else "normal")


# ---------------------------------------------------------------------------
# Gerador de Ícones Vetoriais Procedurais (empacotável em .exe sem arquivos externos)
# ---------------------------------------------------------------------------
_ICON_CACHE: Dict[Tuple[str, int, str], ctk.CTkImage] = {}


def get_icon(name: str, size: int = 18, color: str = "#EDF2F7") -> ctk.CTkImage:
    """
    Desenha ícones geométricos nítidos com supersampling 2x via Pillow,
    garantindo que nenhum recurso externo falte ao compilar com PyInstaller.
    """
    cache_key = (name, size, color)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    scale = 2
    px = size * scale
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    w = max(2, int(1.8 * scale))
    pad = int(2.5 * scale)

    if name == "dashboard":
        # Grade assimétrica de telemetria
        mid = px // 2
        draw.rounded_rectangle([pad, pad, mid - 2, mid + 2], radius=3, outline=color, width=w)
        draw.rounded_rectangle([mid + 2, pad, px - pad, mid - 2], radius=3, outline=color, width=w)
        draw.rounded_rectangle([pad, mid + 6, mid - 2, px - pad], radius=3, outline=color, width=w)
        draw.rounded_rectangle([mid + 2, mid + 2, px - pad, px - pad], radius=3, outline=color, width=w)

    elif name == "console":
        # Terminal prompt >_
        draw.rounded_rectangle([pad, pad + 2, px - pad, px - pad - 2], radius=4, outline=color, width=w)
        draw.line([pad + 6, pad + 9, pad + 12, px // 2], fill=color, width=w)
        draw.line([pad + 12, px // 2, pad + 6, px - pad - 9], fill=color, width=w)
        draw.line([px // 2, px - pad - 8, px - pad - 6, px - pad - 8], fill=color, width=w)

    elif name == "players":
        # Silhueta de jogador / cubo
        cx = px // 2
        r = int(3.5 * scale)
        draw.ellipse([cx - r, pad + 1, cx + r, pad + 1 + 2 * r], outline=color, width=w)
        draw.arc([pad + 2, px // 2 - 1, px - pad - 2, px - pad + 6], start=190, end=350, fill=color, width=w + 1)

    elif name == "properties":
        # Sliders de configuração
        y1, y2, y3 = int(px * 0.28), int(px * 0.5), int(px * 0.72)
        draw.line([pad, y1, px - pad, y1], fill=color, width=w)
        draw.line([pad, y2, px - pad, y2], fill=color, width=w)
        draw.line([pad, y3, px - pad, y3], fill=color, width=w)
        draw.ellipse([int(px * 0.35) - 4, y1 - 4, int(px * 0.35) + 4, y1 + 4], fill=color)
        draw.ellipse([int(px * 0.68) - 4, y2 - 4, int(px * 0.68) + 4, y2 + 4], fill=color)
        draw.ellipse([int(px * 0.45) - 4, y3 - 4, int(px * 0.45) + 4, y3 + 4], fill=color)

    elif name == "backups":
        # Cubo / Cofre de arquivo
        draw.rounded_rectangle([pad + 1, pad + 2, px - pad - 1, px - pad - 1], radius=4, outline=color, width=w)
        cx = px // 2
        draw.line([cx, pad + 6, cx, px - pad - 7], fill=color, width=w)
        draw.line([cx - 6, px // 2 + 2, cx, px - pad - 6], fill=color, width=w)
        draw.line([cx + 6, px // 2 + 2, cx, px - pad - 6], fill=color, width=w)

    elif name == "automation":
        # Pulso / Relógio de automação
        draw.ellipse([pad + 1, pad + 1, px - pad - 1, px - pad - 1], outline=color, width=w)
        cx, cy = px // 2, px // 2
        draw.line([cx, cy - 6, cx, cy], fill=color, width=w)
        draw.line([cx, cy, cx + 5, cy + 3], fill=color, width=w)

    elif name == "files":
        # Pasta de arquivos
        draw.polygon(
            [
                (pad, pad + 4),
                (int(px * 0.42), pad + 4),
                (int(px * 0.52), pad + 8),
                (px - pad, pad + 8),
                (px - pad, px - pad - 2),
                (pad, px - pad - 2),
            ],
            outline=color,
            width=w,
        )

    elif name == "play":
        draw.polygon(
            [(pad + 4, pad + 2), (px - pad - 2, px // 2), (pad + 4, px - pad - 2)],
            fill=color,
        )

    elif name == "stop":
        draw.rounded_rectangle([pad + 3, pad + 3, px - pad - 3, px - pad - 3], radius=2, fill=color)

    elif name == "restart":
        draw.arc([pad + 2, pad + 2, px - pad - 2, px - pad - 2], start=35, end=315, fill=color, width=w + 1)
        draw.polygon(
            [(px - pad - 2, pad + 2), (px - pad - 9, pad + 2), (px - pad - 2, pad + 9)],
            fill=color,
        )

    elif name == "cube":
        # Ícone isométrico do bloco
        cx, cy = px // 2, px // 2
        r = px // 2 - pad
        top = (cx, cy - r)
        left = (cx - r, cy - r // 2)
        right = (cx + r, cy - r // 2)
        mid = (cx, cy)
        bleft = (cx - r, cy + r // 2)
        bright = (cx + r, cy + r // 2)
        bottom = (cx, cy + r)
        draw.polygon([top, right, bottom, left], outline=color, width=w)
        draw.line([left, mid, right], fill=color, width=w)
        draw.line([mid, bottom], fill=color, width=w)

    else:
        draw.ellipse([pad, pad, px - pad, px - pad], outline=color, width=w)

    img_resized = img.resize((size, size), Image.Resampling.LANCZOS)
    ctk_img = ctk.CTkImage(light_image=img_resized, dark_image=img_resized, size=(size, size))
    _ICON_CACHE[cache_key] = ctk_img
    return ctk_img
