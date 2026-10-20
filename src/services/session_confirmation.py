"""Endpoint de confirmação da sessão após o login."""

from core.lcu import request


def confirm_session(port, token):
    """Pede ao cliente que confirme a sessão recém autenticada."""
    return request(port, token, "POST", "/player-session-lifecycle/v1/session/confirm", {})
