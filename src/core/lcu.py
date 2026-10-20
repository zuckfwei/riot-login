"""Comunicação com a API local do Riot Client."""

import base64
import json
import ssl
import time
import urllib.error
import urllib.request

from utils.processes import find_riot_cmdlines


def _argument(command_line, name):
    """Extrai um argumento no formato do cmd do cliente."""
    marker = name + "="
    start = command_line.find(marker)
    if start < 0:
        return ""
    remainder = command_line[start + len(marker):]
    end = remainder.find(" --")
    value = remainder if end < 0 else remainder[:end]
    return value.strip().strip('"')


def find_lcu():
    """Obtém porta e token da primeira instância acessível do cliente."""
    for command_line in find_riot_cmdlines().values():
        port = _argument(command_line, "--app-port")
        token = _argument(command_line, "--remoting-auth-token")
        if port.isdigit() and token:
            return int(port), token
    return None


def wait_for_lcu(seconds=180):
    """Espera o processo publicar porta e token da API local."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        connection = find_lcu()
        if connection:
            return connection
        time.sleep(3)
    return None


def request(port, token, method, path, body=None):
    """Faz uma chamada à API local e devolve código HTTP e corpo decodificado."""
    url = "https://127.0.0.1:" + str(port) + path
    data = json.dumps(body).encode() if body is not None else None
    http_request = urllib.request.Request(url, data=data, method=method)
    credentials = base64.b64encode(("riot:" + token).encode()).decode()
    http_request.add_header("Authorization", "Basic " + credentials)
    http_request.add_header("Content-Type", "application/json")

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(http_request, context=context, timeout=15) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        status = error.code
    except Exception as error:
        return 0, str(error)

    try:
        return status, json.loads(raw)
    except (TypeError, ValueError):
        return status, raw
