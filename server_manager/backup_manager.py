"""
Sistema seguro de Backups do Mundo Minecraft:
Criação em thread separada (com save-off / save-all / save-on se online),
restauração com snapshot de segurança, retenção automática e agendamento.
"""

from __future__ import annotations
from datetime import datetime
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple
import zipfile

from .config import ConfigManager
from .process_manager import ServerProcessManager
from .properties_manager import ServerPropertiesManager


class BackupManager:
    """Gerencia backups compactados (.zip) do mundo e arquivos críticos de configuração."""

    EXTRA_CONFIG_FILES = [
        "server.properties",
        "whitelist.json",
        "ops.json",
        "banned-players.json",
        "banned-ips.json",
        "usercache.json",
    ]

    def __init__(
        self,
        config: ConfigManager,
        process_mgr: ServerProcessManager,
        props_mgr: ServerPropertiesManager,
    ) -> None:
        self.config = config
        self.process_mgr = process_mgr
        self.props_mgr = props_mgr
        self.is_busy = False

    def get_world_name(self) -> str:
        self.props_mgr.load()
        return self.props_mgr.values.get("level-name", "world") or "world"

    def get_world_path(self) -> Path:
        return self.config.server_dir / self.get_world_name()

    def list_backups(self) -> List[Dict[str, object]]:
        b_dir = self.config.backup_dir
        items: List[Dict[str, object]] = []
        if not b_dir.exists():
            return items

        for f in b_dir.glob("*.zip"):
            try:
                stat = f.stat()
                size_mb = round(stat.st_size / (1024 * 1024), 2)
                dt_str = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M:%S")
                items.append(
                    {
                        "name": f.name,
                        "path": f,
                        "size_mb": size_mb,
                        "modified": dt_str,
                        "mtime": stat.st_mtime,
                    }
                )
            except Exception:
                pass

        items.sort(key=lambda x: float(x["mtime"]), reverse=True)
        return items

    def get_world_size_mb(self) -> float:
        wpath = self.get_world_path()
        if not wpath.exists():
            return 0.0
        total = 0
        try:
            for root, _dirs, files in os.walk(wpath):
                for fname in files:
                    try:
                        total += (Path(root) / fname).stat().st_size
                    except OSError:
                        pass
        except Exception:
            pass
        return round(total / (1024 * 1024), 2)

    def create_backup_async(
        self,
        tag: str = "manual",
        progress_cb: Optional[Callable[[float, str], None]] = None,
        done_cb: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        """Executa o backup em background sem travar a UI."""
        if self.is_busy:
            if done_cb:
                done_cb(False, "Uma operação de backup ou restauração já está em andamento.")
            return

        def _worker() -> None:
            self.is_busy = True
            server_was_running = self.process_mgr.is_running()
            world_name = self.get_world_name()
            world_path = self.get_world_path()

            if not world_path.exists():
                self.is_busy = False
                if done_cb:
                    done_cb(False, f"Pasta do mundo '{world_name}' não encontrada em {self.config.server_dir}.")
                return

            try:
                if server_was_running:
                    if progress_cb:
                        progress_cb(0.05, "Sincronizando chunks do servidor (save-all)...")
                    self.process_mgr.send_command("save-off", log_echo=False)
                    self.process_mgr.send_command("save-all flush", log_echo=False)
                    time.sleep(1.5)

                clean_tag = "".join(c for c in tag if c.isalnum() or c in ("-", "_")).strip() or "backup"
                ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                zip_name = f"{world_name}_{ts}_{clean_tag}.zip"
                zip_path = self.config.backup_dir / zip_name

                all_files: List[Tuple[Path, str]] = []
                for root, _dirs, files in os.walk(world_path):
                    for fname in files:
                        if fname == "session.lock":
                            continue
                        full_p = Path(root) / fname
                        rel_p = full_p.relative_to(self.config.server_dir).as_posix()
                        all_files.append((full_p, rel_p))

                for cfg_name in self.EXTRA_CONFIG_FILES:
                    cfg_p = self.config.server_dir / cfg_name
                    if cfg_p.exists():
                        all_files.append((cfg_p, cfg_name))

                total_files = max(1, len(all_files))
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                    for idx, (full_p, arcname) in enumerate(all_files, start=1):
                        try:
                            zf.write(full_p, arcname=arcname)
                        except PermissionError:
                            # Ignora arquivos temporariamente bloqueados pelo SO
                            pass
                        if progress_cb and (idx % 5 == 0 or idx == total_files):
                            pct = 0.1 + 0.85 * (idx / total_files)
                            progress_cb(pct, f"Compactando arquivos ({idx}/{total_files})...")

                self._enforce_retention()
                self.config.set("last_auto_backup_ts", time.time())
                size_mb = round(zip_path.stat().st_size / (1024 * 1024), 2)
                msg = f"Backup '{zip_name}' criado com sucesso ({size_mb} MB)."
                self.process_mgr._emit_event("Backup Concluído", msg, "success")
                if progress_cb:
                    progress_cb(1.0, "Backup concluído!")
                if done_cb:
                    done_cb(True, msg)
            except Exception as exc:
                err_msg = f"Falha ao criar backup: {exc}"
                self.process_mgr._emit_event("Erro no Backup", err_msg, "error")
                if done_cb:
                    done_cb(False, err_msg)
            finally:
                if server_was_running and self.process_mgr.is_running():
                    self.process_mgr.send_command("save-on", log_echo=False)
                self.is_busy = False

        threading.Thread(target=_worker, daemon=True).start()

    def restore_backup_async(
        self,
        zip_path: Path,
        done_cb: Optional[Callable[[bool, str], None]] = None,
    ) -> None:
        """Restaura um arquivo .zip de backup com segurança (requer servidor parado)."""
        if self.is_busy:
            if done_cb:
                done_cb(False, "Outra operação de backup já está em andamento.")
            return

        if self.process_mgr.is_running():
            if done_cb:
                done_cb(False, "Pare o servidor antes de restaurar um backup para evitar corrupção do mundo.")
            return

        def _restore_worker() -> None:
            self.is_busy = True
            world_name = self.get_world_name()
            world_path = self.get_world_path()

            try:
                # 1. Criar cópia de segurança rápida da pasta world atual caso exista
                if world_path.exists():
                    pre_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safety_zip = self.config.backup_dir / f"{world_name}_{pre_ts}_pre-restauracao.zip"
                    with zipfile.ZipFile(safety_zip, "w", compression=zipfile.ZIP_DEFLATED) as szf:
                        for root, _dirs, files in os.walk(world_path):
                            for fname in files:
                                if fname == "session.lock":
                                    continue
                                fp = Path(root) / fname
                                szf.write(fp, arcname=fp.relative_to(self.config.server_dir).as_posix())
                    shutil.rmtree(world_path, ignore_errors=True)

                # 2. Extrair backup selecionado
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(self.config.server_dir)

                self.props_mgr.load()
                msg = f"Backup '{zip_path.name}' restaurado com sucesso!"
                self.process_mgr._emit_event("Backup Restaurado", msg, "warning")
                if done_cb:
                    done_cb(True, msg)
            except Exception as exc:
                err_msg = f"Erro ao restaurar backup: {exc}"
                self.process_mgr._emit_event("Erro na Restauração", err_msg, "error")
                if done_cb:
                    done_cb(False, err_msg)
            finally:
                self.is_busy = False

        threading.Thread(target=_restore_worker, daemon=True).start()

    def delete_backup(self, zip_path: Path) -> Tuple[bool, str]:
        try:
            if zip_path.exists():
                zip_path.unlink()
                return True, f"Backup '{zip_path.name}' removido."
            return False, "Arquivo não encontrado."
        except Exception as exc:
            return False, f"Não foi possível excluir: {exc}"

    def _enforce_retention(self) -> None:
        max_keep = max(1, int(self.config.get("auto_backup_max_keep", 10)))
        backups = self.list_backups()
        if len(backups) > max_keep:
            for old in backups[max_keep:]:
                try:
                    Path(old["path"]).unlink(missing_ok=True)
                except Exception:
                    pass

    def check_scheduled_backup(self) -> None:
        """Verifica se está na hora de rodar o backup agendado (chamado periodicamente pela UI)."""
        if self.is_busy or not self.config.get("auto_backup_enabled", False):
            return

        if self.config.get("auto_backup_only_with_players", False):
            if not self.process_mgr.online_players:
                return

        interval_sec = max(5, int(self.config.get("auto_backup_interval_minutes", 60))) * 60
        last_ts = float(self.config.get("last_auto_backup_ts", 0.0))
        now = time.time()

        if now - last_ts >= interval_sec:
            self.config.set("last_auto_backup_ts", now)
            self.create_backup_async(tag="agendado")
