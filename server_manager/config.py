"""
Gerenciamento de configuração persistente do aplicativo, descoberta do Java
e leitura automática das configurações existentes do servidor (ex: iniciar.bat).
"""

from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_base_dir() -> Path:
    """Retorna o diretório base onde o executável ou script do app está localizado."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def detect_default_server_dir(app_dir: Path) -> Path:
    """
    Detecta automaticamente a pasta do servidor Minecraft:
    procura `server.jar` ou `server.properties` na pasta do app ou nas pastas pai
    (ex: quando o app fica dentro de /ObsidianDeck ou /ObsidianDeck/dist/ObsidianDeck).
    """
    curr = app_dir.resolve()
    for candidate in [curr, curr.parent, curr.parent.parent, curr.parent.parent.parent]:
        if (candidate / "server.jar").exists() or (candidate / "server.properties").exists():
            return candidate
    return curr.parent if curr.name.lower() == "obsidiandeck" else curr


class ConfigManager:
    """Gerencia o arquivo manager_config.json sem modificar arquivos nativos sem permissão."""

    CONFIG_FILENAME = "manager_config.json"

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = (base_dir or get_base_dir()).resolve()
        self.config_path = self.base_dir / self.CONFIG_FILENAME
        self.data: Dict[str, Any] = self._default_config()
        self.load()

    def _detect_initial_ram_from_bat(self, server_dir: Path) -> Tuple[int, int, str]:
        """Lê iniciar.bat se existir para preservar a alocação atual (-Xms / -Xmx)."""
        xms_mb = 2048
        xmx_mb = 4096
        jar_name = "server.jar"
        bat_path = server_dir / "iniciar.bat"
        if bat_path.exists():
            try:
                content = bat_path.read_text(encoding="utf-8", errors="ignore")
                m_xms = re.search(r"-Xms(\d+)([GgMm])", content)
                if m_xms:
                    val = int(m_xms.group(1))
                    xms_mb = val * 1024 if m_xms.group(2).upper() == "G" else val
                m_xmx = re.search(r"-Xmx(\d+)([GgMm])", content)
                if m_xmx:
                    val = int(m_xmx.group(1))
                    xmx_mb = val * 1024 if m_xmx.group(2).upper() == "G" else val
                m_jar = re.search(r"-jar\s+([^\s]+)", content)
                if m_jar:
                    jar_name = m_jar.group(1).strip('"')
            except Exception:
                pass
        return xms_mb, xmx_mb, jar_name

    def _default_config(self) -> Dict[str, Any]:
        default_srv = detect_default_server_dir(self.base_dir)
        xms_mb, xmx_mb, jar_name = self._detect_initial_ram_from_bat(default_srv)
        java_path = self.find_default_java()
        return {
            "server_dir": str(default_srv),
            "jar_file": jar_name,
            "java_path": java_path,
            "xms_mb": xms_mb,
            "xmx_mb": xmx_mb,
            "extra_jvm_args": "-XX:+UseG1GC -XX:+ParallelRefProcEnabled -XX:MaxGCPauseMillis=200",
            "use_extra_jvm_args": False,
            # Automação
            "auto_start_server_on_launch": False,
            "auto_restart_on_crash": True,
            "max_crash_restarts": 3,
            "crash_restart_delay_sec": 10,
            "scheduled_restart_enabled": False,
            "scheduled_restart_time": "04:00",
            "safe_stop_on_exit": True,
            # Backups
            "backup_dir": str(self.base_dir / "backups"),
            "auto_backup_enabled": False,
            "auto_backup_interval_minutes": 60,
            "auto_backup_max_keep": 10,
            "auto_backup_only_with_players": False,
            "last_auto_backup_ts": 0.0,
            # Histórico de Comandos e Jogadores
            "command_history": [
                "list",
                "save-all",
                "weather clear",
                "time set day",
                "whitelist list",
            ],
            "player_history": {},
            "events": [],
        }

    def load(self) -> None:
        if self.config_path.exists():
            try:
                loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update(loaded)
            except Exception:
                pass
        else:
            self.save()

    def save(self) -> None:
        try:
            self.config_path.write_text(
                json.dumps(self.data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        self.data[key] = value
        if auto_save:
            self.save()

    @property
    def server_dir(self) -> Path:
        p = Path(self.data.get("server_dir", str(self.base_dir)))
        return p if p.exists() else self.base_dir

    @property
    def jar_path(self) -> Path:
        return self.server_dir / self.data.get("jar_file", "server.jar")

    @property
    def backup_dir(self) -> Path:
        b_dir = Path(self.data.get("backup_dir") or (self.server_dir / "backups"))
        b_dir.mkdir(parents=True, exist_ok=True)
        return b_dir

    def log_event(self, category: str, message: str, level: str = "info") -> Dict[str, str]:
        """Registra um evento importante no histórico persistente."""
        entry = {
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "category": category,
            "message": message,
            "level": level,
        }
        events: List[Dict[str, str]] = self.data.get("events", [])
        events.insert(0, entry)
        self.data["events"] = events[:150]
        self.save()
        return entry

    def sync_iniciar_bat(self) -> bool:
        """Atualiza opcionalmente o iniciar.bat caso o usuário queira manter compatibilidade externa."""
        bat_path = self.server_dir / "iniciar.bat"
        xms = self.data.get("xms_mb", 2048)
        xmx = self.data.get("xmx_mb", 4096)
        jar = self.data.get("jar_file", "server.jar")
        xms_str = f"{xms // 1024}G" if xms % 1024 == 0 else f"{xms}M"
        xmx_str = f"{xmx // 1024}G" if xmx % 1024 == 0 else f"{xmx}M"
        content = f"@echo off\ntitle Minecraft Vanilla Server\njava -Xms{xms_str} -Xmx{xmx_str} -jar {jar} nogui\npause\n"
        try:
            bat_path.write_text(content, encoding="utf-8")
            return True
        except Exception:
            return False

    @staticmethod
    def find_default_java() -> str:
        """Procura o executável java no PATH ou em pastas padrão do Windows."""
        which_java = shutil.which("java")
        if which_java:
            return which_java

        candidates = []
        java_home = os.environ.get("JAVA_HOME")
        if java_home:
            candidates.append(Path(java_home) / "bin" / "java.exe")

        prog_dirs = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ]
        vendor_folders = ["Java", "Eclipse Adoptium", "Microsoft", "BellSoft", "Zulu"]
        for pdir in prog_dirs:
            if not pdir:
                continue
            base = Path(pdir)
            for vendor in vendor_folders:
                vpath = base / vendor
                if vpath.exists():
                    for java_exe in vpath.rglob("java.exe"):
                        candidates.append(java_exe)

        for cand in candidates:
            if cand.exists():
                return str(cand)
        return "java"

    @staticmethod
    def discover_all_javas() -> List[str]:
        """Lista todas as instalações de Java encontradas no sistema."""
        found: List[str] = []
        w = shutil.which("java")
        if w:
            found.append(w)

        prog_dirs = [
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ]
        for pdir in prog_dirs:
            if not pdir:
                continue
            base = Path(pdir)
            for vendor in ["Java", "Eclipse Adoptium", "Microsoft", "BellSoft", "Zulu", "Common Files\\Oracle\\Java"]:
                vpath = base / vendor
                if vpath.exists():
                    try:
                        for java_exe in vpath.rglob("java.exe"):
                            s = str(java_exe)
                            if s not in found:
                                found.append(s)
                    except Exception:
                        pass
        if not found:
            found.append("java")
        return found

    @staticmethod
    def test_java_version(java_exec: str) -> Tuple[bool, str]:
        """Executa `java -version` e retorna (sucesso, descrição da versão)."""
        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.run(
                [java_exec, "-version"],
                capture_output=True,
                text=True,
                timeout=6,
                creationflags=creationflags,
            )
            output = (proc.stderr or proc.stdout or "").strip()
            if proc.returncode == 0 and output:
                first_line = output.splitlines()[0]
                return True, first_line
            return False, output or "Código de saída inválido ao consultar Java."
        except Exception as exc:
            return False, f"Falha ao executar '{java_exec}': {exc}"
