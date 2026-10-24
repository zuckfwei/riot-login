"""Comunicação com a API local do Riot Client."""

import base64
from functools import lru_cache
import json
import ssl
import time
import urllib.error
import urllib.request

@lru_cache(maxsize=1)
def _local_tls_context():
    """A conexão loopback usa certificado próprio; não carrega CAs públicas inutilmente."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def wait_for_api(port, token, seconds=60):
    """Espera o autenticador ficar acessível na conexão criada pelo programa."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        status, response = request(
            port, token, "GET", "/rso-authenticator/v1/authentication", timeout=2
        )
        if status == 200 and isinstance(response, dict):
            return True
        time.sleep(0.5)
    return False


def request(port, token, method, path, body=None, *, timeout=15):
    """Faz uma chamada à API local e devolve código HTTP e corpo decodificado."""
    url = "https://127.0.0.1:" + str(port) + path
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    http_request = urllib.request.Request(url, data=data, method=method)
    credentials = base64.b64encode(("riot:" + token).encode()).decode()
    http_request.add_header("Authorization", "Basic " + credentials)
    http_request.add_header("Content-Type", "application/json; charset=utf-8")

    context = _local_tls_context()
    # A API é sempre loopback. Não encaminhar suas credenciais a um proxy.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=context)
    )

    try:
        with opener.open(http_request, timeout=timeout) as response:
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
