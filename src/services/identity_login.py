"""Endpoint de login"""

from core.lcu import request


LOGIN_PATH = "/player-session-lifecycle/v1/riot-identity-login"


def submit_login(port, token, username, password, captcha):
    """Envia credenciais somente com a resposta do captcha manual."""
    if not captcha:
        raise ValueError("Token do captcha ausente")

    body = {
        "username": username,
        "password": password,
        "language": "pt_BR",
        "remember": True,
        "captcha": captcha,
    }
    return request(port, token, "POST", LOGIN_PATH, body)
