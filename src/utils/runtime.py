"""Pré-condições para acessar o Riot Client no Windows."""

import ctypes
import os
from pathlib import Path
import subprocess
import sys
import urllib.request


ELEVATION_RELAUNCHED = False


def require_elevated():
    """Relança este script como administrador e encerra a instância atual."""
    if os.name != "nt":
        raise RuntimeError("Este programa exige Windows")
    if ctypes.windll.shell32.IsUserAnAdmin():
        return False

    script = Path(__file__).resolve().parents[1] / "main.py"
    project_dir = script.parent.parent
    arguments = subprocess.list2cmdline([str(script)])
    print("Solicitando permissão de administrador...", flush=True)
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, arguments, str(project_dir), 1
    )
    if result <= 32:
        raise RuntimeError("Não foi possível iniciar como administrador (código " + str(result) + ")")
    return True


def proxy_active():
    """Detecta proxy explícito e PAC sem alterar a configuração do Windows."""
    proxies = urllib.request.getproxies()
    if any(value for key, value in proxies.items() if key.lower() != "no"):
        return True
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            ) as settings:
                try:
                    return bool(winreg.QueryValueEx(settings, "AutoConfigURL")[0])
                except FileNotFoundError:
                    pass
        except OSError:
            pass
    return False


def require_direct_connection():
    """Exige conexão direta antes de iniciar a autenticação."""
    if proxy_active():
        raise RuntimeError("Desative o proxy/PAC antes de resolver o hCaptcha ou fazer login")
