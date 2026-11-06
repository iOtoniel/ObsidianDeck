"""
Gerenciamento assíncrono do processo Java do servidor Minecraft Vanilla,
leitura de logs em tempo real, detecção de eventos e telemetria via psutil.
"""

from __future__ import annotations
from collections import deque
import queue
import re
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Deque, Dict, List, Optional, Tuple
import psutil

from .config import ConfigManager


class ServerState:
    OFFLINE = "OFFLINE"
    STARTING = "INICIANDO"
    ONLINE = "ONLINE"
    STOPPING = "PARANDO"
    CRASHED = "FALHA"


class ServerProcessManager:
    """
    Executa o servidor Minecraft em processo independente (sem janela extra),
    captura stdout/stderr em thread dedicada e coleta telemetria de CPU/RAM.
    """

    # Regexes compatíveis com Minecraft Vanilla 1.7+ até 26.3+
    RE_VERSION = re.compile(r"Starting minecraft server version\s+([^\s]+)", re.IGNORECASE)
    RE_DONE = re.compile(r'Done\s*\(([0-9.,]+s)\)! For help, type "help"')
    RE_LOGIN_IP = re.compile(
        r":\s*([A-Za-z0-9_]{2,16})\[/([0-9a-fA-F.:]+)\]\s+logged in with entity id\s+\d+\s+at\s+\(([^)]+)\)"
    )
    RE_JOIN = re.compile(r":\s*(?:System chat:\s*)?([A-Za-z0-9_]{2,16})\s+joined the game")
    RE_LEAVE = re.compile(r":\s*(?:System chat:\s*)?([A-Za-z0-9_]{2,16})\s+left the game")
    RE_LOST_CONN = re.compile(r":\s*([A-Za-z0-9_]{2,16})\s+lost connection:\s*(.+)")
    RE_LIST = re.compile(r"There are (\d+) of a max of (\d+) players online:\s*(.*)")
    RE_OVERLOAD = re.compile(r"Can't keep up!.*Running (\d+)ms or (\d+) ticks behind")
    RE_EULA = re.compile(r"You need to agree to the EULA in order to run the server", re.IGNORECASE)

    def __init__(self, config: ConfigManager) -> None:
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.ps_proc: Optional[psutil.Process] = None
        self.state: str = ServerState.OFFLINE
        self.server_version: str = self._detect_local_version()
        self.start_time: Optional[float] = None
        self.intentional_stop: bool = False
        self.restart_requested: bool = False
        self.crash_count: int = 0

        # Filas thread-safe para comunicação com a UI
        self.log_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue()
        self.event_queue: "queue.Queue[Dict[str, str]]" = queue.Queue()

        # Histórico circular de logs e telemetria (60 amostras = 60 segundos)
        self.log_history: Deque[Tuple[str, str]] = deque(maxlen=1500)
        self.cpu_history: Deque[float] = deque([0.0] * 60, maxlen=60)
        self.ram_history: Deque[float] = deque([0.0] * 60, maxlen=60)
        self.sys_cpu_history: Deque[float] = deque([0.0] * 60, maxlen=60)

        self.current_cpu_percent: float = 0.0
        self.current_ram_mb: float = 0.0
        self.system_cpu_percent: float = 0.0
        self.system_ram_percent: float = 0.0
        self.system_total_ram_mb: float = round(psutil.virtual_memory().total / (1024 * 1024), 1)

        # Jogadores online em tempo real: {name: {"joined_at": ts, "ip": str, "coords": str}}
        self.online_players: Dict[str, Dict[str, object]] = {}
        self.lock = threading.Lock()

        # Pré-carregar último log do disco para que o Console nunca inicie vazio
        self._preload_latest_log()

    def _detect_local_version(self) -> str:
        versions_dir = self.config.server_dir / "versions"
        if versions_dir.exists():
            try:
                subdirs = [d.name for d in versions_dir.iterdir() if d.is_dir()]
                if subdirs:
                    return subdirs[0]
            except Exception:
                pass
        return "Vanilla"

    def _preload_latest_log(self) -> None:
        latest_log = self.config.server_dir / "logs" / "latest.log"
        if latest_log.exists():
            try:
                lines = latest_log.read_text(encoding="utf-8", errors="replace").splitlines()[-120:]
                for line in lines:
                    level = self._classify_log_line(line)
                    self.log_history.append((line, level))
                    m_ver = self.RE_VERSION.search(line)
                    if m_ver:
                        self.server_version = m_ver.group(1)
            except Exception:
                pass

    @staticmethod
    def _classify_log_line(line: str) -> str:
        upper = line.upper()
        if "/ERROR]" in upper or "/FATAL]" in upper or "EXCEPTION" in upper or "FAILED TO" in upper:
            return "ERROR"
        if "/WARN]" in upper or "CAN'T KEEP UP" in upper or "OFFLINE/INSECURE" in upper:
            return "WARN"
        if "JOINED THE GAME" in upper or "LEFT THE GAME" in upper or "LOGGED IN WITH ENTITY ID" in upper:
            return "PLAYER"
        if "DONE (" in upper or "SAVED THE GAME" in upper or "SAVING CHUNKS" in upper:
            return "SUCCESS"
        if line.startswith("[CMD]"):
            return "CMD"
        return "INFO"

    def check_eula_accepted(self) -> bool:
        eula_file = self.config.server_dir / "eula.txt"
        if not eula_file.exists():
            return False
        try:
            content = eula_file.read_text(encoding="utf-8", errors="ignore")
            return bool(re.search(r"^\s*eula\s*=\s*true", content, re.IGNORECASE | re.MULTILINE))
        except Exception:
            return False

    def accept_eula(self) -> bool:
        eula_file = self.config.server_dir / "eula.txt"
        try:
            now_str = datetime.now().strftime("%a %b %d %H:%M:%S GMT-03:00 %Y")
            content = (
                "#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://aka.ms/MinecraftEULA).\n"
                f"#{now_str}\n"
                "eula=true\n"
            )
            eula_file.write_text(content, encoding="utf-8")
            self._emit_event("Sistema", "EULA da Mojang aceita automaticamente (eula=true).", "info")
            return True
        except Exception as exc:
            self._emit_event("Erro", f"Não foi possível gravar eula.txt: {exc}", "error")
            return False

    def build_launch_command(self) -> List[str]:
        java_exec = self.config.get("java_path", "java") or "java"
        xms = int(self.config.get("xms_mb", 2048))
        xmx = int(self.config.get("xmx_mb", 4096))
        if xms > xmx:
            xms = xmx
        jar_file = self.config.get("jar_file", "server.jar")

        cmd = [java_exec, f"-Xms{xms}M", f"-Xmx{xmx}M"]
        if self.config.get("use_extra_jvm_args", False):
            extra = str(self.config.get("extra_jvm_args", "")).strip()
            if extra:
                cmd.extend(extra.split())
        cmd.extend(["-jar", jar_file, "nogui"])
        return cmd

    def start_server(self) -> Tuple[bool, str]:
        """Inicia o processo Java do servidor de forma assíncrona."""
        if self.is_running():
            return False, "O servidor já está em execução."

        srv_dir = self.config.server_dir
        jar_path = self.config.jar_path
        if not srv_dir.exists():
            return False, f"Diretório do servidor não encontrado: {srv_dir}"
        if not jar_path.exists():
            return False, f"Arquivo JAR não encontrado: {jar_path.name}"

        if not self.check_eula_accepted():
            self.accept_eula()

        cmd = self.build_launch_command()
        self.intentional_stop = False
        self.state = ServerState.STARTING
        with self.lock:
            self.online_players.clear()

        try:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.process = subprocess.Popen(
                cmd,
                cwd=str(srv_dir),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
            self.ps_proc = psutil.Process(self.process.pid)
            # Primeira leitura de cpu_percent inicializa o contador do psutil
            self.ps_proc.cpu_percent(interval=None)
            self.start_time = time.time()

            cmd_str = " ".join(cmd)
            self._push_log(f"[CMD] Iniciando servidor: {cmd_str}", "CMD")
            self._emit_event("Servidor", f"Iniciando servidor ({jar_path.name}) com {self.config.get('xmx_mb')} MB RAM.", "info")

            reader_thread = threading.Thread(target=self._stdout_reader_loop, daemon=True)
            reader_thread.start()
            return True, "Servidor iniciando..."
        except Exception as exc:
            self.state = ServerState.OFFLINE
            self.process = None
            self.ps_proc = None
            msg = f"Falha ao iniciar o processo Java: {exc}"
            self._push_log(f"[ERRO] {msg}", "ERROR")
            self._emit_event("Erro", msg, "error")
            return False, msg

    def stop_server(self, force: bool = False, callback: Optional[Callable[[bool, str], None]] = None) -> None:
        """
        Para o servidor com segurança enviando `save-all` e `stop` via stdin
        em uma thread de trabalho para nunca congelar a interface gráfica.
        """
        if not self.is_running():
            self.state = ServerState.OFFLINE
            if callback:
                callback(True, "Servidor já está parado.")
            return

        self.intentional_stop = True
        self.state = ServerState.STOPPING

        def _stop_worker() -> None:
            proc = self.process
            if not proc:
                self.state = ServerState.OFFLINE
                if callback:
                    callback(True, "Servidor parado.")
                return

            if force:
                self._push_log("[CMD] Forçando encerramento imediato do processo Java...", "WARN")
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
                self._on_process_terminated(forced=True)
                if callback:
                    callback(True, "Processo encerrado forçadamente.")
                return

            self._push_log("[CMD] Salvando mundos e enviando comando 'stop' seguro...", "CMD")
            self.send_command("save-all", log_echo=False)
            time.sleep(0.4)
            self.send_command("stop", log_echo=False)

            try:
                proc.wait(timeout=25)
                if callback:
                    callback(True, "Servidor encerrado com segurança.")
            except subprocess.TimeoutExpired:
                self._push_log("[WARN] Tempo limite de parada excedido (25s). Encerrando processo...", "WARN")
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                if callback:
                    callback(True, "Servidor encerrado após timeout.")

        threading.Thread(target=_stop_worker, daemon=True).start()

    def restart_server(self, callback: Optional[Callable[[bool, str], None]] = None) -> None:
        """Reinicia o servidor aguardando o salvamento completo antes de subir novamente."""
        def _restart_worker() -> None:
            self._emit_event("Servidor", "Reinicialização segura solicitada.", "warning")
            if self.is_running():
                done_event = threading.Event()
                self.stop_server(force=False, callback=lambda _ok, _m: done_event.set())
                done_event.wait(timeout=30)
                time.sleep(1.0)
            ok, msg = self.start_server()
            if callback:
                callback(ok, msg)

        threading.Thread(target=_restart_worker, daemon=True).start()

    def send_command(self, command: str, log_echo: bool = True) -> bool:
        """Envia um comando diretamente ao stdin do servidor Minecraft."""
        cmd_clean = command.strip()
        if not cmd_clean:
            return False
        if cmd_clean.startswith("/"):
            cmd_clean = cmd_clean[1:]

        if not self.is_running() or not self.process or not self.process.stdin:
            self._push_log(f"[WARN] Servidor offline. Comando ignorado: {cmd_clean}", "WARN")
            return False

        try:
            if log_echo:
                self._push_log(f"[CMD] > {cmd_clean}", "CMD")
            self.process.stdin.write(cmd_clean + "\n")
            self.process.stdin.flush()

            # Persistir histórico de comandos
            history: List[str] = self.config.get("command_history", [])
            if cmd_clean in history:
                history.remove(cmd_clean)
            history.insert(0, cmd_clean)
            self.config.set("command_history", history[:50])

            if cmd_clean.lower() == "stop":
                self.intentional_stop = True
                self.state = ServerState.STOPPING
            return True
        except Exception as exc:
            self._push_log(f"[ERRO] Falha ao enviar comando '{cmd_clean}': {exc}", "ERROR")
            return False

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def get_uptime_formatted(self) -> str:
        if not self.is_running() or not self.start_time:
            return "00:00:00"
        elapsed = max(0, int(time.time() - self.start_time))
        hrs, rem = divmod(elapsed, 3600)
        mins, secs = divmod(rem, 60)
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"

    def sample_telemetry(self) -> Dict[str, float]:
        """
        Amostra CPU (%) e RAM (MB) do processo Java (incluindo subprocessos)
        e do sistema operacional. Chamado a cada 1s pela thread principal.
        """
        try:
            sys_cpu = psutil.cpu_percent(interval=None)
            vm = psutil.virtual_memory()
            self.system_cpu_percent = round(sys_cpu, 1)
            self.system_ram_percent = round(vm.percent, 1)
        except Exception:
            pass

        proc_cpu = 0.0
        proc_ram_mb = 0.0

        if self.is_running() and self.ps_proc:
            try:
                if self.ps_proc.is_running():
                    cpu_Count = psutil.cpu_count(logical=True) or 1
                    raw_cpu = self.ps_proc.cpu_percent(interval=None)
                    rss = self.ps_proc.memory_info().rss

                    for child in self.ps_proc.children(recursive=True):
                        try:
                            raw_cpu += child.cpu_percent(interval=None)
                            rss += child.memory_info().rss
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass

                    proc_cpu = min(100.0, round(raw_cpu / cpu_Count, 1))
                    proc_ram_mb = round(rss / (1024 * 1024), 1)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_cpu = 0.0
                proc_ram_mb = 0.0

        self.current_cpu_percent = proc_cpu
        self.current_ram_mb = proc_ram_mb
        self.cpu_history.append(proc_cpu)
        self.ram_history.append(proc_ram_mb)
        self.sys_cpu_history.append(self.system_cpu_percent)

        return {
            "cpu_percent": proc_cpu,
            "ram_mb": proc_ram_mb,
            "sys_cpu_percent": self.system_cpu_percent,
            "sys_ram_percent": self.system_ram_percent,
        }

    # -----------------------------------------------------------------------
    # Internos: Leitura de stdout e análise semântica de eventos
    # -----------------------------------------------------------------------
    def _stdout_reader_loop(self) -> None:
        proc = self.process
        if not proc or not proc.stdout:
            return

        try:
            for raw_line in iter(proc.stdout.readline, ""):
                if not raw_line:
                    break
                line = raw_line.rstrip("\r\n")
                if not line:
                    continue
                level = self._classify_log_line(line)
                self._push_log(line, level)
                self._parse_server_line(line)
        except Exception as exc:
            self._push_log(f"[WARN] Leitor de console interrompido: {exc}", "WARN")
        finally:
            self._on_process_terminated()

    def _parse_server_line(self, line: str) -> None:
        # 1. Versão do servidor
        m_ver = self.RE_VERSION.search(line)
        if m_ver:
            self.server_version = m_ver.group(1)

        # 2. Servidor pronto (ONLINE)
        m_done = self.RE_DONE.search(line)
        if m_done:
            boot_time = m_done.group(1)
            self.state = ServerState.ONLINE
            self.crash_count = 0
            self._emit_event("Servidor Online", f"Mundo carregado e pronto em {boot_time}.", "success")
            return

        # 3. Login com IP e coordenadas
        m_login = self.RE_LOGIN_IP.search(line)
        if m_login:
            name, ip_port, coords = m_login.group(1), m_login.group(2), m_login.group(3)
            ip_only = ip_port.split(":")[0]
            with self.lock:
                self.online_players[name] = {
                    "name": name,
                    "joined_at": time.time(),
                    "ip": ip_only,
                    "coords": coords,
                }
            self._record_player_join(name, ip_only, coords)
            return

        # 4. Join (System chat ou padrão)
        m_join = self.RE_JOIN.search(line)
        if m_join:
            name = m_join.group(1)
            with self.lock:
                if name not in self.online_players:
                    self.online_players[name] = {
                        "name": name,
                        "joined_at": time.time(),
                        "ip": "Local/LAN",
                        "coords": "-",
                    }
                    self._record_player_join(name, "Local/LAN", "-")
            self._emit_event("Jogador Entrou", f"{name} entrou no servidor.", "success")
            return

        # 5. Leave
        m_leave = self.RE_LEAVE.search(line)
        if m_leave:
            name = m_leave.group(1)
            self._handle_player_Disconnect(name)
            return

        m_lost = self.RE_LOST_CONN.search(line)
        if m_lost:
            name, reason = m_lost.group(1), m_lost.group(2)
            self._handle_player_Disconnect(name, reason)
            return

        # 6. Resposta do comando /list
        m_list = self.RE_LIST.search(line)
        if m_list:
            names_raw = m_list.group(3).strip()
            names = [n.strip() for n in names_raw.split(",") if n.strip()] if names_raw else []
            with self.lock:
                # Sincroniza jogadores
                for n in list(self.online_players.keys()):
                    if n not in names:
                        self.online_players.pop(n, None)
                for n in names:
                    if n not in self.online_players:
                        self.online_players[n] = {
                            "name": n,
                            "joined_at": time.time(),
                            "ip": "Ativo",
                            "coords": "-",
                        }
            return

        # 7. Sobrecarga de ticks
        m_over = self.RE_OVERLOAD.search(line)
        if m_over:
            ms, ticks = m_over.group(1), m_over.group(2)
            self._emit_event("Alerta de Performance", f"Servidor atrasado em {ticks} ticks ({ms} ms).", "warning")

    def _record_player_join(self, name: str, ip: str, coords: str) -> None:
        ph: Dict[str, Dict[str, object]] = self.config.get("player_history", {})
        entry = ph.get(name, {})
        joins = int(entry.get("joins", 0)) + 1
        ph[name] = {
            "name": name,
            "last_seen": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "last_ip": ip if ip != "-" else entry.get("last_ip", "-"),
            "last_coords": coords if coords != "-" else entry.get("last_coords", "-"),
            "joins": joins,
            "total_seconds": int(entry.get("total_seconds", 0)),
        }
        self.config.set("player_history", ph)

    def _handle_player_Disconnect(self, name: str, reason: str = "") -> None:
        session_sec = 0
        with self.lock:
            pinfo = self.online_players.pop(name, None)
            if pinfo and isinstance(pinfo.get("joined_at"), (int, float)):
                session_sec = max(0, int(time.time() - float(pinfo["joined_at"])))

        if session_sec > 0:
            ph: Dict[str, Dict[str, object]] = self.config.get("player_history", {})
            entry = ph.get(name, {"name": name, "joins": 1, "total_seconds": 0})
            entry["last_seen"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            entry["total_seconds"] = int(entry.get("total_seconds", 0)) + session_sec
            ph[name] = entry
            self.config.set("player_history", ph)

        if pinfo is not None:
            detail = f" ({reason})" if reason else ""
            self._emit_event("Jogador Saiu", f"{name} desconectou{detail}.", "info")

    def _on_process_terminated(self, forced: bool = False) -> None:
        exit_code = self.process.poll() if self.process else 0
        with self.lock:
            for name in list(self.online_players.keys()):
                self._handle_player_Disconnect(name, "Servidor encerrado")
            self.online_players.clear()

        self.process = None
        self.ps_proc = None
        self.start_time = None
        self.current_cpu_percent = 0.0
        self.current_ram_mb = 0.0

        if self.intentional_stop or forced or exit_code == 0:
            self.state = ServerState.OFFLINE
            self._push_log("[INFO] Processo do servidor finalizado.", "INFO")
            self._emit_event("Servidor Offline", "O servidor foi encerrado.", "info")
        else:
            self.state = ServerState.CRASHED
            self.crash_count += 1
            msg = f"O servidor encerrou inesperadamente (código {exit_code})."
            self._push_log(f"[ERRO] {msg}", "ERROR")
            self._emit_event("Falha Detectada", msg, "error")

            # Verificar auto-restart em caso de crash
            if self.config.get("auto_restart_on_crash", True):
                max_restarts = int(self.config.get("max_crash_restarts", 3))
                delay_sec = int(self.config.get("crash_restart_delay_sec", 10))
                if self.crash_count <= max_restarts:
                    self._push_log(
                        f"[AUTO] Reinicialização automática ({self.crash_count}/{max_restarts}) em {delay_sec}s...",
                        "WARN",
                    )
                    self._emit_event(
                        "Auto-Recuperação",
                        f"Reiniciando servidor automaticamente em {delay_sec}s (tentativa {self.crash_count}/{max_restarts}).",
                        "warning",
                    )
                    threading.Thread(target=self._delayed_crash_restart, args=(delay_sec,), daemon=True).start()

    def _delayed_crash_restart(self, delay_sec: int) -> None:
        for _ in range(delay_sec):
            if self.intentional_stop or self.is_running():
                return
            time.sleep(1)
        if not self.intentional_stop and not self.is_running():
            self.start_server()

    def _push_log(self, line: str, level: str = "INFO") -> None:
        self.log_history.append((line, level))
        self.log_queue.put((line, level))

    def _emit_event(self, category: str, message: str, level: str = "info") -> None:
        entry = self.config.log_event(category, message, level)
        self.event_queue.put(entry)
