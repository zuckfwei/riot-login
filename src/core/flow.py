"""Sequência de troca de conta, login, confirmação e verificação."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from core import browser, client, lcu
from utils.runtime import require_direct_connection
from services import (
    authenticator,
    identity_login,
    player_session,
    session_confirmation,
)


def _login(port, token, config, log, tab):
    """Obtém o challenge e tenta concluir o login até três vezes."""
    username = config["RIOT_USER"]
    password = config["RIOT_PASS"]
    for attempt in range(1, 4):
        require_direct_connection()
        site_key, challenge_data = authenticator.get_challenge(port, token, renew=attempt > 1)
        if not site_key:
            log("Não foi possível obter os dados do hCaptcha")
            return 3
        log("Captcha disponível. Tentativa " + str(attempt) + "/3")
        if attempt == 1:
            browser.render_challenge(tab, site_key)
        captcha_token = browser.solve_challenge(tab, challenge_data, log)
        if not captcha_token:
            continue

        require_direct_connection()
        submitted = time.monotonic()
        status, response = identity_login.submit_login(
            port, token, username, password, "hcaptcha " + captcha_token
        )
        error = response.get("error") if isinstance(response, dict) else None
        log("Envio das credenciais: HTTP " + str(status) + ", erro " + str(error))
        if 200 <= status < 300 and not error:
            status, response = session_confirmation.confirm_session(port, token)
            log("Confirmação da sessão: HTTP " + str(status) + ", " +
                format(time.monotonic() - submitted, ".2f") + " s após o captcha")
            if not 200 <= status < 300:
                log("Falha ao confirmar a sessão: " + json.dumps(response, ensure_ascii=False))
                return 5
            return 0

        log("Resposta do login: " + json.dumps(response, ensure_ascii=False))
        if error == "multifactor":
            log("A conta exige autenticação em duas etapas")
            return 6
        if error and "captcha" not in str(error).lower():
            log("Autenticação recusada após o captcha, erro " + str(error))
            return 4

    log("Login não aceito após três tentativas")
    return 5


def _wait_for_settings(yaml_path, previous, seconds):
    """Aguarda o cliente gravar um token de renovação diferente do anterior."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        current = client.read_settings(yaml_path)
        if "refresh_token" in current and current != previous:
            return current
        time.sleep(0.2)
    return ""


def _wait_for_subject(port, token, seconds=45, expected=None):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        subject = player_session.get_subject(port, token)
        if subject and (expected is None or subject == expected):
            return subject
        time.sleep(0.5)
    return ""


def _verify_login(port, token, config, log, previous):
    """Retorna a conta confirmada somente após o serviço gravar a persistência."""
    subject = _wait_for_subject(port, token)
    if not subject:
        log("Não foi possível confirmar a conta autenticada")
        return ""
    log("Conta autenticada pela API: " + subject)
    updated = _wait_for_settings(config["yaml_path"], previous, 30)
    if not updated:
        log("O serviço não gravou a sessão persistente; interface não aberta")
        return ""
    log("Sessão persistida pelo serviço: " + str(len(updated)) + " bytes")
    return subject


def run(config, log):
    """Reaproveita a API e abre a interface no mesmo processo após o login."""
    require_direct_connection()
    executable = config.get("CLIENTE_EXE", "")
    log("Preparando uma nova sessão para " + config["RIOT_USER"])
    started = time.monotonic()
    service = None
    completed = False
    with ThreadPoolExecutor(max_workers=1) as worker:
        page_job = worker.submit(browser.open_login_page, config["CHROME_EXE"], config["profile_dir"], log)
        try:
            connection = client.prepare_account_change(config["yaml_path"], log)
            if connection:
                pid, port, token, _ = connection
            else:
                log("Iniciando somente o serviço de autenticação")
                service, (port, token) = client.start_service(executable)
                pid = service.pid
                if not lcu.wait_for_api(port, token):
                    log("Falha ao encontrar a API local do cliente")
                    return 2
            player_session.sign_out(port, token, log)
            log("API pronta em " + format(time.monotonic() - started, ".2f") + " s; PID " + str(pid))
            previous = client.read_settings(config["yaml_path"])
            page, tab = page_job.result()
            result = _login(port, token, config, log, tab)
            if result != 0:
                return result
            expected = _verify_login(port, token, config, log, previous)
            if not expected:
                return 5

            opening = time.monotonic()
            log("Abrindo a interface no mesmo serviço, PID " + str(pid))
            client.show_interface(port, token)
            _, port, token, _ = client.wait_for_connection(config["yaml_path"], pid)
            if not _wait_for_subject(port, token, expected=expected):
                log("Não foi possível verificar a conta após abrir a interface")
                return 5
            log("Conta confirmada no Riot Client: " + expected + "; abertura solicitada em " +
                format(time.monotonic() - opening, ".2f") + " s, sem reiniciar o serviço")
            completed = True
            return 0
        finally:
            try:
                page, tab = page_job.result()
            except Exception:
                pass
            else:
                browser.close_challenge(page, tab)
            if service is not None and not completed:
                client.stop_service(service)
