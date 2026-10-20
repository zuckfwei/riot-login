"""Endpoint que informa o estado da sessão autenticada."""

from core.lcu import request
from utils.tokens import jwt_payload


def get_subject(port, token):
    """Lê o identificador da conta do token de acesso da sessão."""
    _, response = request(port, token, "GET", "/player-session-lifecycle/v1/session")
    if not isinstance(response, dict):
        return ""
    access_token = response.get("accessToken") or {}
    if not isinstance(access_token, dict):
        return ""
    token_value = access_token.get("token") or ""
    if not token_value:
        return ""
    return str(jwt_payload(token_value).get("sub") or "")
