"""Busca a sitekey e o rqdata do challenge"""

import time

from core.lcu import request


AUTHENTICATION_PATH = "/rso-authenticator/v1/authentication"
START_PATH = AUTHENTICATION_PATH + "/riot-identity/start"


def start_authentication(port, token):
    """Cria apenas o desafio, sem enviar usuário ou senha (schema do cliente)."""
    return request(port, token, "POST", START_PATH, {
        "language": "pt_BR",
        "productId": "riot-client",
        "state": "auth",
    })


def _read_challenge(response):
    """Extrai sitekey e rqdata da resposta da API."""
    if not isinstance(response, dict):
        return "", ""
    if response.get("type") not in (None, "auth"):
        return "", ""

    captcha = response.get("captcha")
    if not isinstance(captcha, dict):
        return "", ""

    hcaptcha = captcha.get("hcaptcha")
    if not isinstance(hcaptcha, dict):
        return "", ""

    # "key" é a sitekey do widget; "data" é o rqdata desta tentativa.
    return hcaptcha.get("key") or "", hcaptcha.get("data") or ""


def wait_for_challenge(port, token):
    """Espera o challenge aparecer na API local, por até oito consultas."""
    # O serviço publica o desafio após a inicialização da autenticação.
    for attempt in range(8):
        # Espera apenas entre consultas, nunca depois da última.
        if attempt > 0:
            time.sleep(2)

        _, response = request(port, token, "GET", AUTHENTICATION_PATH)
        site_key, challenge_data = _read_challenge(response)
        if site_key and challenge_data:
            return site_key, challenge_data
    return "", ""


def get_challenge(port, token, renew=False):
    """Reaproveita o desafio inicial; inicia outro somente quando necessário."""
    if not renew:
        _, response = request(port, token, "GET", AUTHENTICATION_PATH)
        challenge = _read_challenge(response)
        if all(challenge):
            return challenge

    status, response = start_authentication(port, token)
    if not 200 <= status < 300:
        return "", ""
    challenge = _read_challenge(response)
    return challenge if all(challenge) else wait_for_challenge(port, token)
