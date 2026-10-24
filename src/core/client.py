"""Processos, credenciais locais e persistência do Riot Client."""

import ctypes
from ctypes import wintypes
import secrets
import socket
import subprocess
import time
from pathlib import Path

from core import lcu


def _service_running(pid):
    """Distingue um lockfile antigo de um serviço vivo cuja API não respondeu."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    ]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return False
    try:
        image = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(image))
        return (
            bool(kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)))
            and Path(image.value).name.lower() == "riotclientservices.exe"
        )
    finally:
        kernel.CloseHandle(handle)


def read_settings(yaml_path):
    """Lê a configuração persistida pelo cliente, se existir."""
    try:
        return Path(yaml_path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def start_service(executable, *, headless=True):
    """Inicia a API com porta e segredo próprios, sem depender da leitura do PEB."""
    if not executable or not Path(executable).is_file():
        raise RuntimeError("CLIENTE_EXE inválido no .env")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    token = secrets.token_urlsafe(24)
    arguments = [executable, "--app-port=" + str(port), "--remoting-auth-token=" + token]
    if headless:
        arguments.append("--headless")
    process = subprocess.Popen(arguments)
    return process, (port, token)


def stop_service(service):
    """Encerra somente o processo criado pelo programa."""
    if service.poll() is None:
        service.terminate()
        try:
            service.wait(timeout=10)
        except subprocess.TimeoutExpired:
            service.kill()
            service.wait(timeout=5)


def find_connection(yaml_path, *, allow_unavailable=False):
    """Lê as portas publicadas pelo próprio cliente, incluindo o modo de bandeja."""
    config_dir = Path(yaml_path).parent.parent / "Config"
    background = None
    unavailable = False
    for lockfile in sorted(config_dir.glob("lockfile*")):
        try:
            name, pid, port, token, scheme = lockfile.read_text(encoding="utf-8").strip().split(":")
            pid, port = int(pid), int(port)
            if name != "Riot Client" or scheme != "https" or not token or not 0 < port < 65536:
                continue
        except (OSError, ValueError):
            continue
        status, body = lcu.request(port, token, "GET", "/rso-authenticator/v1/authentication", timeout=1)
        if status == 200 and isinstance(body, dict):
            return pid, port, token, True
        if status == 401:
            if allow_unavailable:
                unavailable = True
                continue
            raise RuntimeError("O cliente está aberto, mas recusou a credencial da API local")
        if status:
            status, body = lcu.request(port, token, "GET", "/help", timeout=1)
            if status == 200 and isinstance(body, dict):
                if "PostRiotclientappV1NewArgs" in body.get("functions", {}):
                    background = pid, port, token, False
                    continue
        unavailable = unavailable or _service_running(pid)
    if unavailable and background is None and not allow_unavailable:
        raise RuntimeError("O serviço está aberto, mas sua API não respondeu; dados de sessão preservados")
    return background


def send_arguments(port, token, arguments):
    """Entrega argumentos ao processo existente, sem lançar outro executável."""
    status, response = lcu.request(port, token, "POST", "/PostRiotclientappV1NewArgs", arguments)
    if not 200 <= status < 300:
        raise RuntimeError("O cliente recusou a mudança de modo: HTTP " + str(status) + ", " + str(response))


def show_interface(port, token):
    """Solicita a interface também quando o serviço foi iniciado com --headless."""
    status, response = lcu.request(port, token, "POST", "/riot-client-lifecycle/v1/show")
    if not 200 <= status < 300:
        raise RuntimeError("Não foi possível abrir a interface: HTTP " + str(status) + ", " + str(response))


def wait_for_connection(yaml_path, pid, *, seconds=30):
    """A mudança entre bandeja e autenticação pode substituir porta e segredo."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        connection = find_connection(yaml_path, allow_unavailable=True)
        if connection and connection[0] == pid and connection[3]:
            return connection
        time.sleep(0.2)
    raise RuntimeError("O serviço existente não ativou a API de autenticação")


def prepare_account_change(yaml_path, log):
    """Reaproveita o cliente; remove o YAML apenas quando não há serviço acessível."""
    connection = find_connection(yaml_path)
    if connection:
        pid, port, token, ready = connection
        log("Reaproveitando RiotClientServices, PID " + str(pid))
        if not ready:
            log("Ativando a autenticação no serviço de bandeja")
            send_arguments(port, token, ["--headless"])
            connection = wait_for_connection(yaml_path, pid)
        return connection

    yaml_path = Path(yaml_path)
    if yaml_path.exists():
        yaml_path.unlink()
        log("Sem serviço aberto; configuração de sessão anterior removida")
    return None
