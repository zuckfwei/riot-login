"""Endpoint de identidade da conta atualmente aberta."""

from core.lcu import request


def get_userinfo(port, token):
    """Obtém os dados da conta exibida pelo cliente, quando disponíveis."""
    status, response = request(port, token, "GET", "/riot-client-auth/v1/userinfo")
    if status == 200 and isinstance(response, dict):
        return response
    return None
