"""
Leitura, validação e persistência do arquivo `server.properties` do Minecraft Vanilla,
preservando comentários e indicando alterações que exigem reinicialização.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PropertySpec:
    key: str
    label: str
    category: str
    prop_type: str  # "bool", "int", "enum", "str"
    description: str
    requires_restart: bool = True
    options: Optional[List[str]] = None
    min_val: Optional[int] = None
    max_val: Optional[int] = None


# Especificação das propriedades mais importantes do Minecraft Vanilla (incluindo 26.3)
PROPERTY_SPECS: Dict[str, PropertySpec] = {
    # --- Geral & Rede ---
    "motd": PropertySpec(
        "motd",
        "Mensagem do Servidor (MOTD)",
        "Geral & Rede",
        "str",
        "Texto exibido na lista de servidores do Minecraft. Suporta códigos de cor (§a, §e, §d).",
        requires_restart=True,
    ),
    "server-port": PropertySpec(
        "server-port",
        "Porta do Servidor (TCP/UDP)",
        "Geral & Rede",
        "int",
        "Porta padrão de conexão (padrão: 25565). Deve estar entre 1 e 65535.",
        requires_restart=True,
        min_val=1,
        max_val=65535,
    ),
    "server-ip": PropertySpec(
        "server-ip",
        "Endereço IP de Bind",
        "Geral & Rede",
        "str",
        "Deixe em branco para escutar em todas as interfaces de rede locais.",
        requires_restart=True,
    ),
    "max-players": PropertySpec(
        "max-players",
        "Máximo de Jogadores Simultâneos",
        "Geral & Rede",
        "int",
        "Número máximo de jogadores que podem entrar ao mesmo tempo.",
        requires_restart=True,
        min_val=1,
        max_val=500,
    ),
    "online-mode": PropertySpec(
        "online-mode",
        "Modo Online (Autenticação Mojang/Microsoft)",
        "Segurança & Acesso",
        "bool",
        "Se desativado (false), permite contas sem autenticação oficial (modo offline/LAN).",
        requires_restart=True,
    ),
    "white-list": PropertySpec(
        "white-list",
        "Ativar Whitelist (Lista de Permissão)",
        "Segurança & Acesso",
        "bool",
        "Apenas jogadores listados na Whitelist ou OPs poderão entrar.",
        requires_restart=False,
    ),
    "enforce-whitelist": PropertySpec(
        "enforce-whitelist",
        "Forçar Whitelist Imediata",
        "Segurança & Acesso",
        "bool",
        "Expulsa imediatamente jogadores conectados que forem removidos da whitelist.",
        requires_restart=True,
    ),
    "enforce-secure-profile": PropertySpec(
        "enforce-secure-profile",
        "Exigir Perfil Assinado (Chat Seguro)",
        "Segurança & Acesso",
        "bool",
        "Exige chaves públicas assinadas pela Mojang. Desative se usar online-mode=false.",
        requires_restart=True,
    ),
    "op-permission-level": PropertySpec(
        "op-permission-level",
        "Nível de Permissão Padrão de OP",
        "Segurança & Acesso",
        "enum",
        "1: Ignora spawn protection | 2: Comandos de jogo | 3: Kick/Ban/OP | 4: Controle total (stop).",
        requires_restart=True,
        options=["1", "2", "3", "4"],
    ),
    # --- Jogabilidade & Mundo ---
    "gamemode": PropertySpec(
        "gamemode",
        "Modo de Jogo Padrão",
        "Jogabilidade & Mundo",
        "enum",
        "Define o modo de jogo para novos jogadores ao entrarem no mundo.",
        requires_restart=True,
        options=["survival", "creative", "adventure", "spectator"],
    ),
    "difficulty": PropertySpec(
        "difficulty",
        "Dificuldade do Mundo",
        "Jogabilidade & Mundo",
        "enum",
        "Define o dano causado por criaturas e a mecânica de fome.",
        requires_restart=False,
        options=["peaceful", "easy", "normal", "hard"],
    ),
    "hardcore": PropertySpec(
        "hardcore",
        "Modo Hardcore (Morte Permanente)",
        "Jogabilidade & Mundo",
        "bool",
        "Se ativado, jogadores que morrerem ficam em modo espectador permanentemente.",
        requires_restart=True,
    ),
    "force-gamemode": PropertySpec(
        "force-gamemode",
        "Forçar Modo de Jogo Padrão ao Entrar",
        "Jogabilidade & Mundo",
        "bool",
        "Força todos os jogadores para o modo de jogo padrão sempre que conectarem.",
        requires_restart=True,
    ),
    "allow-flight": PropertySpec(
        "allow-flight",
        "Permitir Voo no Modo Survival",
        "Jogabilidade & Mundo",
        "bool",
        "Evita que jogadores sejam expulsos por 'Flying is not enabled' (útil com Elytra/lag).",
        requires_restart=True,
    ),
    "spawn-protection": PropertySpec(
        "spawn-protection",
        "Raio de Proteção do Spawn (Blocos)",
        "Jogabilidade & Mundo",
        "int",
        "Raio ao redor do ponto inicial onde apenas OPs podem quebrar blocos (0 desativa).",
        requires_restart=True,
        min_val=0,
        max_val=512,
    ),
    "level-name": PropertySpec(
        "level-name",
        "Nome da Pasta do Mundo",
        "Jogabilidade & Mundo",
        "str",
        "Nome do diretório onde o mundo principal é salvo (padrão: world).",
        requires_restart=True,
    ),
    "level-seed": PropertySpec(
        "level-seed",
        "Semente do Mundo (Seed)",
        "Jogabilidade & Mundo",
        "str",
        "Seed usada na geração de novos mundos.",
        requires_restart=True,
    ),
    "generate-structures": PropertySpec(
        "generate-structures",
        "Gerar Estruturas (Vilas, Templos, Fortalezas)",
        "Jogabilidade & Mundo",
        "bool",
        "Define se estruturas naturais serão geradas em novos chunks.",
        requires_restart=True,
    ),
    # --- Performance & Chunks ---
    "view-distance": PropertySpec(
        "view-distance",
        "Distância de Renderização (Chunks)",
        "Performance & Chunks",
        "int",
        "Quantidade de chunks enviados aos jogadores em cada direção (padrão: 10, mín: 2, máx: 32).",
        requires_restart=True,
        min_val=2,
        max_val=32,
    ),
    "simulation-distance": PropertySpec(
        "simulation-distance",
        "Distância de Simulação de Entidades (Chunks)",
        "Performance & Chunks",
        "int",
        "Distância máxima onde entidades, redstone e plantações são processadas (2 a 32).",
        requires_restart=True,
        min_val=2,
        max_val=32,
    ),
    "pause-when-empty-seconds": PropertySpec(
        "pause-when-empty-seconds",
        "Pausar Servidor Vazio Após (Segundos)",
        "Performance & Chunks",
        "int",
        "Pausa o processamento do mundo quando não há jogadores online (0 para nunca pausar).",
        requires_restart=True,
        min_val=0,
        max_val=86400,
    ),
    "player-idle-timeout": PropertySpec(
        "player-idle-timeout",
        "Tempo Limite de Inatividade AFK (Minutos)",
        "Performance & Chunks",
        "int",
        "Expulsa jogadores parados por mais de X minutos (0 desativa).",
        requires_restart=False,
        min_val=0,
        max_val=1440,
    ),
    "max-tick-time": PropertySpec(
        "max-tick-time",
        "Tempo Máximo de Tick Watchdog (ms)",
        "Performance & Chunks",
        "int",
        "Tempo máximo que 1 tick pode demorar antes de derrubar o servidor (-1 desativa watchdog).",
        requires_restart=True,
        min_val=-1,
        max_val=600000,
    ),
    "network-compression-threshold": PropertySpec(
        "network-compression-threshold",
        "Limite de Compressão de Pacotes (Bytes)",
        "Performance & Chunks",
        "int",
        "Tamanho mínimo de pacote para comprimir (padrão: 256, -1 desativa compressão).",
        requires_restart=True,
        min_val=-1,
        max_val=65536,
    ),
    "sync-chunk-writes": PropertySpec(
        "sync-chunk-writes",
        "Escrita Síncrona de Chunks no Disco",
        "Performance & Chunks",
        "bool",
        "Garante maior segurança contra corrupção, mas pode causar leve impacto em discos lentos.",
        requires_restart=True,
    ),
}


class ServerPropertiesManager:
    """Lê, valida e grava o arquivo server.properties preservando a formatação original."""

    def __init__(self, server_dir: Path) -> None:
        self.server_dir = server_dir
        self.raw_lines: List[str] = []
        self.values: Dict[str, str] = {}
        self.loaded_snapshot: Dict[str, str] = {}
        self.load()

    @property
    def file_path(self) -> Path:
        return self.server_dir / "server.properties"

    def set_server_dir(self, server_dir: Path) -> None:
        self.server_dir = server_dir
        self.load()

    def load(self) -> Dict[str, str]:
        self.raw_lines.clear()
        self.values.clear()
        if not self.file_path.exists():
            self.loaded_snapshot = {}
            return self.values

        try:
            text = self.file_path.read_text(encoding="utf-8", errors="replace")
            self.raw_lines = text.splitlines()
            for line in self.raw_lines:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if "=" in stripped:
                    k, v = stripped.split("=", 1)
                    self.values[k.strip()] = v.strip()
            self.loaded_snapshot = dict(self.values)
        except Exception:
            pass
        return self.values

    def validate_property(self, key: str, value: str) -> Tuple[bool, str]:
        """Valida um valor individual de acordo com as regras da propriedade."""
        spec = PROPERTY_SPECS.get(key)
        val_str = str(value).strip()

        if not spec:
            # Inferência automática para propriedades avançadas não catalogadas
            orig = self.loaded_snapshot.get(key, "")
            if orig in ("true", "false") and val_str.lower() not in ("true", "false"):
                return False, f"'{key}' exige 'true' ou 'false'."
            return True, ""

        if spec.prop_type == "bool":
            if val_str.lower() not in ("true", "false"):
                return False, f"{spec.label}: valor deve ser 'true' ou 'false'."
        elif spec.prop_type == "int":
            try:
                num = int(val_str)
            except ValueError:
                return False, f"{spec.label}: deve ser um número inteiro válido."
            if spec.min_val is not None and num < spec.min_val:
                return False, f"{spec.label}: valor mínimo permitido é {spec.min_val}."
            if spec.max_val is not None and num > spec.max_val:
                return False, f"{spec.label}: valor máximo permitido é {spec.max_val}."
        elif spec.prop_type == "enum" and spec.options:
            if val_str not in spec.options:
                return False, f"{spec.label}: escolha entre {', '.join(spec.options)}."

        return True, ""

    def get_restart_required_changes(self, candidate_values: Dict[str, str]) -> List[str]:
        """Retorna a lista de chaves alteradas que exigem reinicialização do servidor."""
        changed_restart: List[str] = []
        for k, new_v in candidate_values.items():
            old_v = self.loaded_snapshot.get(k, "")
            if str(new_v).strip() != str(old_v).strip():
                spec = PROPERTY_SPECS.get(k)
                if spec is None or spec.requires_restart:
                    changed_restart.append(k)
        return changed_restart

    def save(self, updated_values: Dict[str, str]) -> Tuple[bool, str, List[str]]:
        """
        Valida todos os valores e salva em server.properties preservando comentários.
        Retorna (sucesso, mensagem, lista_chaves_que_exigem_restart).
        """
        for k, v in updated_values.items():
            ok, err = self.validate_property(k, v)
            if not ok:
                return False, err, []

        restart_keys = self.get_restart_required_changes(updated_values)
        self.values.update({k: str(v).strip() for k, v in updated_values.items()})

        written_keys = set()
        new_lines: List[str] = []

        for line in self.raw_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _ = stripped.split("=", 1)
                k = k.strip()
                if k in self.values:
                    new_lines.append(f"{k}={self.values[k]}")
                    written_keys.add(k)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        for k, v in self.values.items():
            if k not in written_keys:
                new_lines.append(f"{k}={v}")

        try:
            self.file_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            self.raw_lines = new_lines
            self.loaded_snapshot = dict(self.values)
            return True, "Configurações salvas com sucesso em server.properties.", restart_keys
        except Exception as exc:
            return False, f"Erro ao gravar server.properties: {exc}", []
