"""
Gerenciamento completo de Jogadores para Minecraft Vanilla:
Conectados, Whitelist, OPs, Banimentos, Kick, Mensagens Globais e Histórico.
Funciona tanto com o servidor ONLINE (via comandos de console) quanto OFFLINE (via JSON).
"""

from __future__ import annotations
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

from .config import ConfigManager
from .process_manager import ServerProcessManager


def generate_offline_uuid(username: str) -> str:
    """
    Calcula o UUID v3 oficial utilizado pelo Minecraft Vanilla quando online-mode=false:
    MD5("OfflinePlayer:" + username) formatado como UUID v3.
    """
    raw = f"OfflinePlayer:{username}".encode("utf-8")
    md5_bytes = bytearray(hashlib.md5(raw).digest())
    md5_bytes[6] = (md5_bytes[6] & 0x0F) | 0x30  # Version 3
    md5_bytes[8] = (md5_bytes[8] & 0x3F) | 0x80  # Variant RFC 4122
    return str(uuid.UUID(bytes=bytes(md5_bytes)))


class PlayerManager:
    """Sincroniza usercache.json, whitelist.json, ops.json e banned-players.json."""

    def __init__(self, config: ConfigManager, process_mgr: ServerProcessManager) -> None:
        self.config = config
        self.process_mgr = process_mgr

    @property
    def server_dir(self) -> Path:
        return self.config.server_dir

    def _read_json_list(self, filename: str) -> List[Dict[str, Any]]:
        p = self.server_dir / filename
        if not p.exists():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _write_json_list(self, filename: str, data: List[Dict[str, Any]]) -> bool:
        p = self.server_dir / filename
        try:
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except Exception:
            return False

    def get_usercache(self) -> List[Dict[str, Any]]:
        return self._read_json_list("usercache.json")

    def resolve_uuid(self, username: str) -> str:
        """Busca o UUID do jogador no usercache.json ou gera o UUID offline compatível."""
        uname_lower = username.strip().lower()
        for entry in self.get_usercache():
            if str(entry.get("name", "")).lower() == uname_lower and entry.get("uuid"):
                return str(entry["uuid"])
        return generate_offline_uuid(username.strip())

    def get_whitelist(self) -> List[Dict[str, Any]]:
        return self._read_json_list("whitelist.json")

    def get_ops(self) -> List[Dict[str, Any]]:
        return self._read_json_list("ops.json")

    def get_banned_players(self) -> List[Dict[str, Any]]:
        return self._read_json_list("banned-players.json")

    def get_banned_ips(self) -> List[Dict[str, Any]]:
        return self._read_json_list("banned-ips.json")

    # -----------------------------------------------------------------------
    # Ações de Jogadores (Online + Offline)
    # -----------------------------------------------------------------------
    def add_whitelist(self, username: str) -> Tuple[bool, str]:
        name = username.strip()
        if not name:
            return False, "Informe o nome do jogador."

        wl = self.get_whitelist()
        if not any(str(x.get("name", "")).lower() == name.lower() for x in wl):
            wl.append({"uuid": self.resolve_uuid(name), "name": name})
            self._write_json_list("whitelist.json", wl)

        if self.process_mgr.is_running():
            self.process_mgr.send_command(f"whitelist add {name}")
            self.process_mgr.send_command("whitelist reload")

        self.config.log_event("Whitelist", f"Jogador '{name}' adicionado à whitelist.", "info")
        return True, f"'{name}' adicionado à Whitelist."

    def remove_whitelist(self, username: str) -> Tuple[bool, str]:
        name = username.strip()
        wl = [x for x in self.get_whitelist() if str(x.get("name", "")).lower() != name.lower()]
        self._write_json_list("whitelist.json", wl)

        if self.process_mgr.is_running():
            self.process_mgr.send_command(f"whitelist remove {name}")
            self.process_mgr.send_command("whitelist reload")

        self.config.log_event("Whitelist", f"Jogador '{name}' removido da whitelist.", "info")
        return True, f"'{name}' removido da Whitelist."

    def add_op(self, username: str, level: int = 4) -> Tuple[bool, str]:
        name = username.strip()
        if not name:
            return False, "Informe o nome do jogador."

        ops = self.get_ops()
        if not any(str(x.get("name", "")).lower() == name.lower() for x in ops):
            ops.append(
                {
                    "uuid": self.resolve_uuid(name),
                    "name": name,
                    "level": level,
                    "bypassesPlayerLimit": False,
                }
            )
            self._write_json_list("ops.json", ops)

        if self.process_mgr.is_running():
            self.process_mgr.send_command(f"op {name}")

        self.config.log_event("Operador (OP)", f"Permissão OP concedida a '{name}'.", "info")
        return True, f"'{name}' agora é Operador (OP)."

    def remove_op(self, username: str) -> Tuple[bool, str]:
        name = username.strip()
        ops = [x for x in self.get_ops() if str(x.get("name", "")).lower() != name.lower()]
        self._write_json_list("ops.json", ops)

        if self.process_mgr.is_running():
            self.process_mgr.send_command(f"deop {name}")

        self.config.log_event("Operador (OP)", f"Permissão OP removida de '{name}'.", "info")
        return True, f"Permissão OP removida de '{name}'."

    def kick_player(self, username: str, reason: str = "Expulso pelo administrador") -> Tuple[bool, str]:
        name = username.strip()
        if not self.process_mgr.is_running():
            return False, "O servidor precisa estar online para expulsar (Kick) um jogador."
        self.process_mgr.send_command(f"kick {name} {reason}")
        self.config.log_event("Moderação", f"Jogador '{name}' expulso ({reason}).", "warning")
        return True, f"Comando kick enviado para '{name}'."

    def ban_player(self, username: str, reason: str = "Banido pelo administrador") -> Tuple[bool, str]:
        name = username.strip()
        if not name:
            return False, "Informe o nome do jogador."

        bans = self.get_banned_players()
        if not any(str(x.get("name", "")).lower() == name.lower() for x in bans):
            bans.append(
                {
                    "uuid": self.resolve_uuid(name),
                    "name": name,
                    "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S -0300"),
                    "source": "Server",
                    "expires": "forever",
                    "reason": reason or "Banido pelo administrador",
                }
            )
            self._write_json_list("banned-players.json", bans)

        if self.process_mgr.is_running():
            self.process_mgr.send_command(f"ban {name} {reason}")

        self.config.log_event("Banimento", f"Jogador '{name}' banido ({reason}).", "error")
        return True, f"'{name}' foi banido."

    def pardon_player(self, username: str) -> Tuple[bool, str]:
        name = username.strip()
        bans = [x for x in self.get_banned_players() if str(x.get("name", "")).lower() != name.lower()]
        self._write_json_list("banned-players.json", bans)

        if self.process_mgr.is_running():
            self.process_mgr.send_command(f"pardon {name}")

        self.config.log_event("Moderação", f"Banimento de '{name}' removido (pardon).", "info")
        return True, f"Banimento de '{name}' removido."

    def broadcast_message(self, message: str, use_title: bool = False) -> Tuple[bool, str]:
        msg = message.strip()
        if not msg:
            return False, "Digite uma mensagem para enviar."
        if not self.process_mgr.is_running():
            return False, "O servidor está offline. Inicie-o para enviar mensagens globais."

        self.process_mgr.send_command(f"say {msg}")
        if use_title:
            escaped = json.dumps({"text": msg, "color": "gold"})
            self.process_mgr.send_command(f"title @a actionbar {escaped}")
        return True, "Mensagem global enviada aos jogadores."

    def get_all_known_players(self) -> List[Dict[str, Any]]:
        """
        Combina dados do usercache.json, histórico de sessões do gerenciador,
        status online atual, OP, Whitelist e Ban.
        """
        online_map = dict(self.process_mgr.online_players)
        ops_set = {str(x.get("name", "")).lower() for x in self.get_ops()}
        wl_set = {str(x.get("name", "")).lower() for x in self.get_whitelist()}
        ban_set = {str(x.get("name", "")).lower() for x in self.get_banned_players()}
        history_map: Dict[str, Dict[str, Any]] = self.config.get("player_history", {})

        known: Dict[str, Dict[str, Any]] = {}

        # 1. Carregar de usercache.json
        for uc in self.get_usercache():
            name = str(uc.get("name", "")).strip()
            if not name:
                continue
            key = name.lower()
            hist = history_map.get(name, {})
            known[key] = {
                "name": name,
                "uuid": uc.get("uuid", "-"),
                "online": name in online_map,
                "is_op": key in ops_set,
                "is_whitelisted": key in wl_set,
                "is_banned": key in ban_set,
                "last_seen": hist.get("last_seen") or uc.get("expiresOn", "Registrado no cache"),
                "last_ip": online_map.get(name, {}).get("ip") or hist.get("last_ip", "-"),
                "joins": int(hist.get("joins", 1)),
                "total_seconds": int(hist.get("total_seconds", 0)),
            }

        # 2. Mesclar do histórico do gerenciador e jogadores online
        for name, hist in history_map.items():
            key = name.lower()
            if key not in known:
                known[key] = {
                    "name": name,
                    "uuid": self.resolve_uuid(name),
                    "online": name in online_map,
                    "is_op": key in ops_set,
                    "is_whitelisted": key in wl_set,
                    "is_banned": key in ban_set,
                    "last_seen": hist.get("last_seen", "-"),
                    "last_ip": online_map.get(name, {}).get("ip") or hist.get("last_ip", "-"),
                    "joins": int(hist.get("joins", 1)),
                    "total_seconds": int(hist.get("total_seconds", 0)),
                }

        for name, oinfo in online_map.items():
            key = name.lower()
            if key not in known:
                known[key] = {
                    "name": name,
                    "uuid": self.resolve_uuid(name),
                    "online": True,
                    "is_op": key in ops_set,
                    "is_whitelisted": key in wl_set,
                    "is_banned": key in ban_set,
                    "last_seen": "Online agora",
                    "last_ip": oinfo.get("ip", "-"),
                    "joins": 1,
                    "total_seconds": 0,
                }
            else:
                known[key]["online"] = True
                known[key]["last_seen"] = "Online agora"

        result = list(known.values())
        result.sort(key=lambda x: (not x["online"], x["name"].lower()))
        return result
