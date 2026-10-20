"""Processos, credenciais locais e persistência do Riot Client."""

import shutil
import subprocess
import time
from pathlib import Path

ALL_PROCESSES = (
    "LeagueClientUxRender.exe",
    "LeagueClientUx.exe",
    "LeagueClient.exe",
    "RiotClientUxRender.exe",
    "RiotClientUx.exe",
    "Riot Client.exe",
    "RiotClientElectron.exe",
    "RiotClientHelper.exe",
    "RiotClientServices.exe",
)
INTERFACE_PROCESSES = (
    "Riot Client.exe",
    "RiotClientUx.exe",
    "RiotClientUxRender.exe",
    "RiotClientElectron.exe",
    "RiotClientHelper.exe",
)


def read_settings(yaml_path):
    """Lê a configuração persistida pelo cliente, se existir."""
    try:
        return Path(yaml_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def start_client(executable):
    """Abre o serviço do Riot Client configurado no .env."""
    if not executable or not Path(executable).is_file():
        raise RuntimeError("CLIENTE_EXE inválido no .env")
    subprocess.Popen([executable])


def stop_client():
    """Encerra os processos do cliente antes da troca de conta."""
    for executable in ALL_PROCESSES:
        for _ in range(6):
            result = subprocess.run(
                ["taskkill", "/F", "/IM", executable], capture_output=True, text=True
            )
            if result.returncode != 0:
                break
            time.sleep(0.6)
    time.sleep(1.2)


def restart_interface(client_executable):
    """Relança apenas a interface caso ela não grave a sessão persistente."""
    for executable in INTERFACE_PROCESSES:
        subprocess.run(
            ["taskkill", "/F", "/IM", executable], capture_output=True, text=True
        )
        time.sleep(0.4)
    time.sleep(1.5)
    start_client(client_executable)


def prepare_account_change(yaml_path, log):
    """Remove os dados locais da sessão anterior sem criar backup."""
    stop_client()
    yaml_path = Path(yaml_path)
    for name in ("Cookies", "Sessions"):
        directory = yaml_path.parent / name
        if directory.is_dir():
            shutil.rmtree(directory, ignore_errors=True)
            log("Dados locais removidos, " + name)

    result = subprocess.run(["cmdkey", "/list"], capture_output=True, text=True)
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("Target:") and any(
            name in stripped.lower() for name in ("riot", "legion")
        ):
            target = stripped[len("Target:"):].strip()
            subprocess.run(["cmdkey", "/delete:" + target], capture_output=True, text=True)
            log("Credencial local removida, " + target)

    if yaml_path.exists():
        yaml_path.unlink()
        log("Configuração local anterior removida")
