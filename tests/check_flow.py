"""Verifica o fluxo sem abrir o cliente nem usar credenciais reais."""

import sys
import tempfile
from contextlib import ExitStack, redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core import browser, config as config_module, flow
from services import authenticator, identity_login
import main as entrypoint


CONFIG = {
    "RIOT_USER": "example",
    "RIOT_PASS": "secret",
    "CLIENTE_EXE": "client.exe",
    "CHROME_EXE": "chrome.exe",
    "yaml_path": Path("settings.yaml"),
    "output_dir": Path("out"),
    "profile_dir": Path("browser-profile"),
}


def test_known_env_fields():
    """A leitura mantém o sinal de igual da senha e ignora chaves extras."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / ".env").write_text(
            "# comentário=ignorado\n"
            "RIOT_USER=example\n"
            "RIOT_PASS=part1=part2\n"
            "CLIENTE_EXE=C:/Riot/client.exe\n"
            "CHROME_EXE=\n"
            "EXTRA=ignorado\n",
            encoding="utf-8",
        )
        with patch.object(config_module, "ROOT", root):
            loaded = config_module.load_config()

    assert loaded["RIOT_USER"] == "example"
    assert loaded["RIOT_PASS"] == "part1=part2"
    assert loaded["CHROME_EXE"] == ""
    assert loaded["output_dir"] == root / "out"
    assert "EXTRA" not in loaded
    assert "root" not in loaded


def test_challenge_waits_for_complete_response():
    """O autenticador pode responder antes de publicar o desafio completo."""
    responses = [
        (200, {"captcha": {}}),
        (200, {"captcha": {"hcaptcha": {"key": "site-key", "data": "rqdata"}}}),
    ]
    with patch.object(authenticator, "request", side_effect=responses) as request:
        with patch.object(authenticator.time, "sleep") as sleep:
            challenge = authenticator.wait_for_challenge(1234, "token")

    assert challenge == ("site-key", "rqdata")
    assert request.call_count == 2
    sleep.assert_called_once_with(2)


def test_challenge_returns_without_waiting_after_last_query():
    """A falha na oitava consulta não acrescenta uma espera inútil."""
    with patch.object(authenticator, "request", return_value=(200, {"captcha": {}})) as request:
        with patch.object(authenticator.time, "sleep") as sleep:
            challenge = authenticator.wait_for_challenge(1234, "token")

    assert challenge == ("", "")
    assert request.call_count == 8
    assert sleep.call_count == 7


def test_login_stages():
    """A primeira etapa gera o challenge; a segunda exige um captcha."""
    with patch.object(identity_login, "request", return_value=(200, {})) as request:
        identity_login.start_login(1234, "token", "example", "secret")
        assert "captcha" not in request.call_args.args[-1]

        try:
            identity_login.submit_login(1234, "token", "example", "secret", None)
        except ValueError as error:
            assert "captcha ausente" in str(error)
        else:
            raise AssertionError("Era esperado um erro para captcha ausente")

        assert request.call_count == 1
        identity_login.submit_login(1234, "token", "example", "secret", "hcaptcha abc")
        assert request.call_args.args[-1]["captcha"] == "hcaptcha abc"


def test_login_always_restarts():
    """Cada execução válida limpa a sessão local e faz o login configurado."""
    with ExitStack() as stack:
        stack.enter_context(patch.object(
            flow.lcu, "find_lcu", side_effect=AssertionError("Não deve consultar sessão anterior")
        ))
        prepare = stack.enter_context(patch.object(flow.client, "prepare_account_change"))
        stack.enter_context(patch.object(flow.client, "start_client"))
        stack.enter_context(patch.object(flow.lcu, "wait_for_lcu", return_value=(1234, "token")))
        stack.enter_context(patch.object(flow.userinfo, "get_userinfo", return_value=None))
        login = stack.enter_context(patch.object(flow, "_login", return_value=0))
        stack.enter_context(patch.object(flow, "_verify_login", return_value=0))

        result = flow.run(CONFIG, lambda message: None)
        assert result == 0
        prepare.assert_called_once()
        login.assert_called_once()


def test_account_change_without_backup():
    """A troca remove o YAML anterior sem gravar uma cópia."""
    with tempfile.TemporaryDirectory() as directory:
        yaml_path = Path(directory) / "RiotGamesPrivateSettings.yaml"
        yaml_path.write_text("refresh_token: old", encoding="utf-8")
        messages = []
        with patch.object(flow.client, "stop_client"):
            with patch.object(flow.client.subprocess, "run") as run:
                run.return_value.stdout = ""
                flow.client.prepare_account_change(yaml_path, messages.append)

        assert not yaml_path.exists()
        assert not (Path(directory) / "backup").exists()
        assert "Configuração local anterior removida" in messages


def test_successful_login():
    """O fluxo envia o token do captcha, confirma a sessão e aguarda o YAML."""
    messages = []
    with ExitStack() as stack:
        stack.enter_context(patch.object(flow.lcu, "wait_for_lcu", return_value=(1234, "token")))
        stack.enter_context(patch.object(flow.userinfo, "get_userinfo", return_value=None))
        stack.enter_context(patch.object(flow.client, "prepare_account_change"))
        stack.enter_context(patch.object(flow.client, "start_client"))
        stack.enter_context(patch.object(
            flow.authenticator, "wait_for_challenge", return_value=("site-key", "data")
        ))
        start = stack.enter_context(patch.object(
            flow.identity_login, "start_login", return_value=(400, {"error": "captcha token missing"})
        ))
        submit = stack.enter_context(patch.object(
            flow.identity_login, "submit_login", return_value=(200, {"error": None})
        ))
        stack.enter_context(patch.object(
            flow.browser, "open_challenge", return_value=(MagicMock(), MagicMock())
        ))
        stack.enter_context(patch.object(
            flow.browser, "solve_challenge", return_value="captcha-token"
        ))
        close = stack.enter_context(patch.object(flow.browser, "close_challenge"))
        confirm = stack.enter_context(patch.object(
            flow.session_confirmation, "confirm_session", return_value=(204, "")
        ))
        stack.enter_context(patch.object(
            flow.player_session, "get_subject", return_value="account-id"
        ))
        stack.enter_context(patch.object(
            flow.client, "read_settings",
            side_effect=["old", "new refresh_token", "new refresh_token"]
        ))

        result = flow.run(CONFIG, messages.append)
        assert result == 0
        start.assert_called_once_with(1234, "token", "example", "secret")
        submit.assert_called_once()
        assert submit.call_args.args[-1] == "hcaptcha captcha-token"
        confirm.assert_called_once_with(1234, "token")
        close.assert_called_once()
        assert any("manter conectado" in message for message in messages)


def test_rejected_credentials():
    """Uma senha recusada encerra o fluxo antes de abrir o navegador."""
    with ExitStack() as stack:
        stack.enter_context(patch.object(flow.lcu, "wait_for_lcu", return_value=(1234, "token")))
        stack.enter_context(patch.object(flow.userinfo, "get_userinfo", return_value=None))
        stack.enter_context(patch.object(flow.client, "prepare_account_change"))
        stack.enter_context(patch.object(flow.client, "start_client"))
        stack.enter_context(patch.object(
            flow.identity_login, "start_login", return_value=(400, {"error": "invalid credentials"})
        ))
        open_browser = stack.enter_context(patch.object(flow.browser, "open_challenge"))

        result = flow.run(CONFIG, lambda message: None)
        assert result == 4
        open_browser.assert_not_called()


def test_interface_restart():
    """A interface é relançada quando a configuração não muda a tempo."""
    with ExitStack() as stack:
        stack.enter_context(patch.object(
            flow.session_confirmation, "confirm_session", return_value=(204, "")
        ))
        stack.enter_context(patch.object(
            flow.player_session, "get_subject", return_value="account-id"
        ))
        stack.enter_context(patch.object(
            flow.client, "read_settings", side_effect=["old", "new refresh_token"]
        ))
        wait_settings = stack.enter_context(patch.object(
            flow, "_wait_for_settings", side_effect=["", "new refresh_token"]
        ))
        restart = stack.enter_context(patch.object(flow.client, "restart_interface"))
        wait_lcu = stack.enter_context(patch.object(
            flow.lcu, "wait_for_lcu", return_value=(5678, "new-token")
        ))

        result = flow._verify_login(1234, "token", CONFIG, lambda message: None)
        assert result == 0
        assert wait_settings.call_count == 2
        restart.assert_called_once_with("client.exe")
        wait_lcu.assert_called_once_with(200)


def test_browser_fallback():
    """Um caminho antigo no .env usa o Chrome instalado no Windows."""
    expected = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
    messages = []
    with patch.dict(browser.os.environ, {"PROGRAMFILES": "C:/Program Files"}):
        with patch.object(browser.Path, "is_file", autospec=True) as is_file:
            is_file.side_effect = lambda path: path == expected
            found = browser._find_browser("D:/old/bin/chrome.exe", messages.append)
            automatic = browser._find_browser("", messages.append)

    assert found == str(expected)
    assert automatic == str(expected)
    assert messages


def test_browser_missing():
    """Uma instalação ausente produz uma mensagem clara."""
    empty_roots = {"PROGRAMFILES": "", "PROGRAMFILES(X86)": "", "LOCALAPPDATA": ""}
    with patch.dict(browser.os.environ, empty_roots):
        try:
            browser._find_browser("", lambda message: None)
        except RuntimeError as error:
            assert "Chrome não encontrado" in str(error)
        else:
            raise AssertionError("Era esperado um aviso de Chrome ausente")

    output = StringIO()
    with ExitStack() as stack:
        stack.enter_context(patch.object(entrypoint, "load_config", return_value={"output_dir": Path("out")}))
        stack.enter_context(patch.object(entrypoint.Path, "mkdir"))
        stack.enter_context(patch.object(entrypoint.logging, "basicConfig"))
        stack.enter_context(patch.object(entrypoint.logging, "exception"))
        stack.enter_context(patch.object(entrypoint, "run", side_effect=RuntimeError("Chrome não encontrado")))
        with redirect_stderr(output):
            result = entrypoint.main()

    assert result == 9
    assert "Chrome não encontrado" in output.getvalue()


def test_missing_dependency_stops_before_login():
    """Uma dependência ausente não deve limpar a sessão local."""
    output = StringIO()
    with ExitStack() as stack:
        stack.enter_context(patch.object(entrypoint, "load_config", return_value={"output_dir": Path("out")}))
        stack.enter_context(patch.object(entrypoint.Path, "mkdir"))
        stack.enter_context(patch.object(entrypoint.logging, "basicConfig"))
        stack.enter_context(patch.object(entrypoint.importlib.util, "find_spec", return_value=None))
        run = stack.enter_context(patch.object(entrypoint, "run"))
        with redirect_stderr(output):
            result = entrypoint.main()

    assert result == 9
    assert "DrissionPage" in output.getvalue()
    run.assert_not_called()


def test_unexpected_error_is_visible():
    """Uma falha imprevista também aparece no terminal."""
    output = StringIO()
    with ExitStack() as stack:
        stack.enter_context(patch.object(entrypoint, "load_config", return_value={"output_dir": Path("out")}))
        stack.enter_context(patch.object(entrypoint.Path, "mkdir"))
        stack.enter_context(patch.object(entrypoint.logging, "basicConfig"))
        stack.enter_context(patch.object(entrypoint.logging, "exception"))
        stack.enter_context(patch.object(entrypoint.importlib.util, "find_spec", return_value=object()))
        stack.enter_context(patch.object(entrypoint, "run", side_effect=ValueError("falha de teste")))
        with redirect_stderr(output):
            result = entrypoint.main()

    assert result == 9
    assert "falha de teste" in output.getvalue()


if __name__ == "__main__":
    test_known_env_fields()
    test_challenge_waits_for_complete_response()
    test_challenge_returns_without_waiting_after_last_query()
    test_login_stages()
    test_login_always_restarts()
    test_account_change_without_backup()
    test_successful_login()
    test_rejected_credentials()
    test_interface_restart()
    test_browser_fallback()
    test_browser_missing()
    test_missing_dependency_stops_before_login()
    test_unexpected_error_is_visible()
    print("Fluxo validado sem acessar o Riot Client")
