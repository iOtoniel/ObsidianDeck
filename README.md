# Obsidian Deck — Minecraft Vanilla Server Manager

Gerenciador gráfico completo, responsivo e de baixo consumo de recursos desenvolvido em **Python + CustomTkinter** para administrar servidores **Minecraft Java Vanilla** no Windows preservando todos os mundos, logs e arquivos existentes.

---

## Principais Funcionalidades

1. **Visão Geral (Dashboard) & Telemetria em Tempo Real**
   - Monitoramento em tempo real do **processo Java do servidor** (CPU % e memória RSS MB) e do sistema hospedeiro via `psutil`.
   - Gráficos de osciloscópio duplos nativos em `tk.Canvas` (alta fluidez e consumo mínimo de RAM/CPU, sem peso do Matplotlib).
   - Controle rápido de alocação de memória (`-Xms` e `-Xmx`), flags G1GC otimizadas, sincronização opcional com `iniciar.bat` e atalhos rápidos de mundo (`save-all`, `time set day/night`, `weather clear`).
2. **Controle Seguro do Processo Java**
   - Execução em background (`CREATE_NO_WINDOW`) sem travar a interface gráfica.
   - Parada segura (`save-all` seguido de `stop` via `stdin`), reinicialização automatizada e proteção ao fechar a janela.
3. **Console Integrado ao Vivo**
   - Destaque semântico por cores (`INFO`, `WARN`, `ERROR`, `PLAYER`, `CMD`, `SUCCESS`).
   - Filtros instantâneos (*Todos*, *Erros & Avisos*, *Jogadores*, *Comandos*), busca textual, histórico de comandos navegável com as setas `↑` / `↓` e exportação de logs.
4. **Gerenciamento de Jogadores, Whitelist, OP e Moderação**
   - Leitura automática do `usercache.json`, `whitelist.json`, `ops.json` e `banned-players.json` (compatível com UUIDs oficiais e modo offline `online-mode=false`).
   - Funciona tanto com o servidor **online** (via comandos em tempo real) quanto **offline** (editando os arquivos JSON diretamente).
   - Ações de 1 clique para Whitelist, OP, Modo Criativo/Survival, Kick, Ban/Desbanir e Anúncio Global (`/say` + `title actionbar`).
5. **Editor Visual do `server.properties`**
   - Propriedades organizadas por categoria (*Principais*, *Geral & Rede*, *Jogabilidade & Mundo*, *Performance & Chunks*, *Segurança & Acesso*, *Todas*).
   - Validação de tipos e limites numéricos em tempo real, preservando todos os comentários originais do arquivo.
   - Aviso automático de alterações que exigem reinicialização com botão **"Salvar e Reiniciar Servidor Agora"**.
6. **Backups Seguros do Mundo**
   - Criação de backups `.zip` em thread dedicada. Se o servidor estiver online, executa `save-off` → `save-all flush` → compacta → `save-on` automaticamente.
   - Restauração segura com criação automática de um snapshot `_pre-restauracao.zip` antes de substituir o mundo.
   - Agendamento periódico configurável e retenção automática dos últimos *N* backups.
7. **Automação & Watchdog**
   - Auto-iniciar servidor ao abrir o gerenciador e opção para iniciar o gerenciador junto com o login do Windows.
   - Detecção de quedas inesperadas (*crash*) com reinicialização automática configurável.
   - Reinicialização diária programada (`HH:MM`) e confirmação de `eula.txt`.
8. **Gerenciador de Arquivos, Logs Compactados e Java**
   - Seleção do diretório do servidor, escolha do arquivo `.jar` e autodescoberta/teste de instalações do Java (`java -version`).
   - Visualizador e editor integrado para arquivos `.properties`, `.json`, `.txt`, `.bat`, `.log` e descompactação em memória de logs antigos `.log.gz`.

---

## Como Executar

### 1. Instalar dependências
No terminal PowerShell ou Prompt de Comando na pasta do servidor:
```powershell
py -m pip install -r requirements.txt
```

### 2. Iniciar o Gerenciador
Dê dois cliques em **`iniciar_painel.bat`** ou execute:
```powershell
py main.py
```

---

## Como Gerar o Executável (`.exe`) com PyInstaller

Você pode gerar o executável autônomo clicando duas vezes em **`build_exe.bat`** ou executando no terminal:

```powershell
# Executável em pasta (inicialização instantânea - Recomendado):
py -m PyInstaller --noconfirm --onedir --windowed --name "ObsidianDeck" --collect-all customtkinter main.py

# Ou arquivo único (onefile):
py -m PyInstaller --noconfirm --onefile --windowed --name "ObsidianDeck" --collect-all customtkinter main.py
```

> **Nota:** Caso utilize o modo `--onefile`, coloque o `ObsidianDeck.exe` gerado (que estará na pasta `dist\`) dentro da pasta raiz do seu servidor Minecraft (junto ao `server.jar`), ou selecione a pasta do servidor na aba **Arquivos & Java**.
