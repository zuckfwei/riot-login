"""Endpoint de login"""

from core.lcu import request


LOGIN_PATH = "/player-session-lifecycle/v1/riot-identity-login"


def _login_body(username, password):
    """Monta os campos usados nas duas etapas do login."""
    return {
        "username": username,
        "password": password,
        "language": "pt_BR",
        "remember": True,
    }


def start_login(port, token, username, password):
    """Inicia a tentativa para que o cliente gere o challenge."""
    return request(port, token, "POST", LOGIN_PATH, _login_body(username, password))


def submit_login(port, token, username, password, captcha):
    """Envia o captcha para concluir a tentativa de login."""
    if not captcha:
        raise ValueError("Token do captcha ausente")

    body = _login_body(username, password)
    body["captcha"] = captcha
    return request(port, token, "POST", LOGIN_PATH, body)
