"""Sequência de troca de conta, login, confirmação e verificação."""

import json
import time

from core import browser, client, lcu
from services import (
    authenticator,
    identity_login,
    player_session,
    rso_session,
    session_confirmation,
    userinfo,
)


def _login(port, token, config, log):
    """Obtém o challenge e tenta concluir o login até três vezes."""
    username = config["RIOT_USER"]
    password = config["RIOT_PASS"]
    page = tab = None

    try:
        for attempt in range(1, 4):
            status, response = identity_login.start_login(port, token, username, password)
            raw = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
            log("Preparação do login " + str(attempt) + ", HTTP " + str(status) +
                ", resposta " + raw[:180])
            if any(word in raw.lower() for word in ("incorrect", "credential", "invalid")):
                log("Credencial recusada pelo serviço de autenticação")
                return 4

            site_key, challenge_data = authenticator.wait_for_challenge(port, token)
            if not site_key:
                log("Não foi possível obter os dados do hCaptcha")
                return 3

            if page is None:
                page, tab = browser.open_challenge(
                    config.get("CHROME_EXE", ""), config["profile_dir"], site_key, log
                )
            captcha_token = browser.solve_challenge(tab, challenge_data, log)
            if not captcha_token:
                continue

            for captcha in ("hcaptcha " + captcha_token, captcha_token):
                status, response = identity_login.submit_login(
                    port, token, username, password, captcha
                )
                error = response.get("error") if isinstance(response, dict) else None
                log("Login HTTP " + str(status) + ", erro " + str(error))
                if 200 <= status < 400 and not error:
                    return 0

            if isinstance(response, dict) and response.get("error") == "multifactor":
                log("Autenticação em duas etapas exigida para " + username)
                return 6
            if status >= 400 and error and "captcha" not in str(error):
                log("Credencial recusada após o captcha, erro " + str(error))
                return 4

        log("Login não aceito após três tentativas")
        return 5
    finally:
        browser.close_challenge(page, tab)


def _wait_for_settings(yaml_path, previous, seconds):
    """Aguarda o cliente gravar um token de renovação diferente do anterior."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        current = client.read_settings(yaml_path)
        if "refresh_token" in current and current != previous:
            return current
        time.sleep(3)
    return ""


def _verify_login(port, token, config, log):
    """Confirma a sessão e observa a atualização da configuração local."""
    status, _ = session_confirmation.confirm_session(port, token)
    log("Confirmação HTTP " + str(status))
    previous = client.read_settings(config["yaml_path"])

    subject = ""
    deadline = time.time() + 45
    while time.time() < deadline:
        subject = player_session.get_subject(port, token)
        if subject:
            log("Sessão aceita, identificador " + subject[:8])
            break
        time.sleep(2)

    updated = _wait_for_settings(config["yaml_path"], previous, 75)
    if updated:
        log("Configuração de sessão atualizada, " + str(len(updated)) + " bytes")
    else:
        log("Configuração não atualizada. Reiniciando apenas a interface")
        client.restart_interface(config.get("CLIENTE_EXE", ""))
        connection = lcu.wait_for_lcu(200)
        if connection:
            port, token = connection
        updated = _wait_for_settings(config["yaml_path"], previous, 90)
        if updated:
            log("Configuração atualizada após reiniciar a interface, " +
                str(len(updated)) + " bytes")

    final = client.read_settings(config["yaml_path"])
    if subject and "refresh_token" in final:
        log("Login concluído com manter conectado, " + config["RIOT_USER"])
    elif subject:
        log("Login concluído, mas manter conectado ainda não foi gravado")
    else:
        log("Não foi possível confirmar o token de acesso. Confira o cliente")
    return 0


def run(config, log):
    """Executa o mesmo fluxo de login do programa original."""
    username = config.get("RIOT_USER", "")
    password = config.get("RIOT_PASS", "")
    if not username or not password:
        print("Preencha RIOT_USER e RIOT_PASS no .env")
        return 2

    log("=== Login " + username + " iniciado às " + time.strftime("%H:%M:%S") + " ===")
    client.prepare_account_change(config["yaml_path"], log)
    client.start_client(config.get("CLIENTE_EXE", ""))
    log("Cliente iniciado")
    connection = lcu.wait_for_lcu(180)
    if not connection:
        log("Falha ao encontrar a API local do cliente")
        return 2
    port, token = connection
    log("API local na porta " + str(port))

    if userinfo.get_userinfo(port, token):
        log("Sessão local restaurada automaticamente. Encerrando sessão RSO")
        rso_session.delete_session(port, token)
        time.sleep(3)

    result = _login(port, token, config, log)
    if result != 0:
        return result
    result = _verify_login(port, token, config, log)
    log("=== Fim ===")
    return result
