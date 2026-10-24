"""Endpoint que informa o estado da sessão autenticada."""

from core.lcu import request
from utils.tokens import jwt_payload


SESSION_PATH = "/player-session-lifecycle/v1/session"


def sign_out(port, token, log):
    """Deixa o próprio cliente encerrar a conta e limpar o remember me."""
    status, state = request(port, token, "GET", SESSION_PATH)
    if status != 200 or not isinstance(state, dict):
        raise RuntimeError("Não foi possível consultar a sessão antes do login: HTTP " + str(status))
    persistence = state.get("persistence") or {}
    has_account = state.get("accessToken") or state.get("puuid") or persistence.get("puuid")
    if not has_account and state.get("loginState") == "PendingLoginStrategy":
        log("Cliente já está sem conta autenticada")
        return
    status, response = request(port, token, "DELETE", SESSION_PATH)
    log("Signout da conta anterior: HTTP " + str(status))
    if not 200 <= status < 300:
        raise RuntimeError("Signout recusado pelo cliente: " + str(response))


def get_subject(port, token):
    """Obtém o identificador da conta autenticada na sessão local."""
    _, response = request(port, token, "GET", SESSION_PATH)
    if not isinstance(response, dict):
        return ""
    access_token = response.get("accessToken") or {}
    if not isinstance(access_token, dict):
        return ""
    token_value = access_token.get("token") or ""
    if not token_value:
        return ""
    return str(jwt_payload(token_value).get("sub") or "")
