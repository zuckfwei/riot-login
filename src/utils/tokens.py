import base64
import json


def jwt_payload(token):
    """Decodifica o payload do JWT"""
    try:
        encoded = token.split(".")[1]
        encoded += "=" * (-len(encoded) % 4)
        return json.loads(base64.urlsafe_b64decode(encoded))
    except (IndexError, ValueError, TypeError):
        return {}
