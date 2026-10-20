"""Busca a sitekey e o rqdata do challenge"""

import time

from core.lcu import request


def _read_challenge(response):
    """Extrai sitekey e rqdata da resposta da API."""
    if not isinstance(response, dict):
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
    # O POST de login cria o challenge, mas a API pode demorar a publicá-lo.
    for attempt in range(8):
        # Espera apenas entre consultas, nunca depois da última.
        if attempt > 0:
            time.sleep(2)

        _, response = request(port, token, "GET", "/rso-authenticator/v1/authentication")
        site_key, challenge_data = _read_challenge(response)
        if site_key and challenge_data:
            return site_key, challenge_data
    return "", ""
