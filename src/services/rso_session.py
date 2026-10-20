"""Endpoint de encerramento da sessão RSO local."""

from core.lcu import request


def delete_session(port, token):
    """Remove uma sessão restaurada automaticamente antes do novo login."""
    return request(port, token, "DELETE", "/rso-auth/v1/session")
