"""Navegador usado para abrir o login da Riot e resolver o hCaptcha."""

import json
import os
import time
from pathlib import Path


FIND_SIGN_IN = """
var elements = Array.from(document.querySelectorAll('a,button'));
var target = elements.find(function (element) {
    var text = ((element.innerText || '') + ' ' +
                (element.getAttribute('href') || '')).toLowerCase();
    return text.includes('sign in') || text.includes('sign-in') ||
           text.includes('entrar');
});
if (!target) return 'nada';
var href = target.getAttribute('href') || '';
if (href.startsWith('http')) return 'href:' + href;
if (href.startsWith('/')) return 'href:https://www.riotgames.com' + href;
target.click();
return 'click';
"""


def _find_browser(configured_path, log):
    """Usa o caminho configurado ou uma instalação comum do Chrome."""
    if configured_path and Path(configured_path).is_file():
        return configured_path

    for root in (
        os.environ.get("PROGRAMFILES"),
        os.environ.get("PROGRAMFILES(X86)"),
        os.environ.get("LOCALAPPDATA"),
    ):
        if not root:
            continue
        candidate = Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"
        if candidate.is_file():
            if configured_path:
                log("CHROME_EXE indisponível. Usando o Chrome instalado no Windows")
            else:
                log("Usando o Chrome instalado no Windows")
            return str(candidate)
    raise RuntimeError("Chrome não encontrado. Instale o navegador ou corrija CHROME_EXE")


def open_challenge(browser_executable, profile_dir, site_key, log):
    """Abre a página oficial de login e mostra o widget de hCaptcha."""
    from DrissionPage import ChromiumOptions, ChromiumPage

    browser_executable = _find_browser(browser_executable, log)

    options = ChromiumOptions()
    options.set_browser_path(browser_executable)
    options.set_local_port(9333)
    options.set_user_data_path(str(profile_dir))
    options.set_argument("--no-first-run")
    options.set_argument("--no-default-browser-check")

    page = ChromiumPage(addr_or_opts=options)
    tab = page.new_tab("https://www.riotgames.com/en")
    log("Navegador pronto")

    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            ready = tab.run_js("return document.readyState") == "complete"
        except Exception:
            ready = False
        if "riotgames.com" in str(tab.url or "") and ready:
            break
        time.sleep(1)

    action = tab.run_js(FIND_SIGN_IN)
    log("Link de entrada, " + str(action)[:200])
    if isinstance(action, str) and action.startswith("href:"):
        tab.run_js("location.href = " + json.dumps(action[5:]) + ";")

    deadline = time.time() + 45
    while time.time() < deadline:
        if "authenticate.riotgames.com" in str(tab.url or ""):
            break
        time.sleep(1)
    log("Página de login, " + str(tab.url or "")[:110])

    deadline = time.time() + 40
    loaded = False
    while time.time() < deadline:
        try:
            loaded = bool(tab.run_js("return !!window.hcaptcha"))
        except Exception:
            loaded = False
        if loaded:
            break
        time.sleep(1)
    log("hCaptcha carregado, " + str(loaded))
    if not loaded:
        raise RuntimeError("hcaptcha.js não carregou")

    render_widget = """
if (window.__WID2) {
    hcaptcha.reset(window.__WID2);
    return String(window.__WID2);
}
var container = document.createElement('div');
container.id = 'zyon-hc2';
container.style.cssText = 'position:fixed;right:10px;bottom:10px;' +
    'z-index:2147483647;background:#fff;border:2px solid #d33;padding:6px';
document.body.appendChild(container);
window.__WID2 = hcaptcha.render(container, {sitekey: SITE_KEY, theme: 'light'});
return String(window.__WID2);
""".replace("SITE_KEY", json.dumps(site_key))
    widget_id = tab.run_js(render_widget)
    log("Widget ID " + str(widget_id))
    return page, tab


def solve_challenge(tab, challenge_data, log, timeout=180):
    """Aguarda o token do hCaptcha e permite resolução manual se necessário."""
    execute_widget = """
window.__H2 = {tok: null, err: null};
try {
    hcaptcha.reset(window.__WID2);
    hcaptcha.setData(window.__WID2, {rqdata: CHALLENGE_DATA});
    window.hcaptcha.execute(window.__WID2, {async: true})
        .then(function (result) { window.__H2.tok = result && result.response; })
        .catch(function (error) {
            window.__H2.err = String(error && error.message || error);
        });
} catch (error) {
    window.__H2.err = String(error);
}
""".replace("CHALLENGE_DATA", json.dumps(challenge_data))
    tab.run_js(execute_widget)
    log("hCaptcha iniciado. Resolva a verificação na janela se ela aparecer")

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        try:
            state = json.loads(tab.run_js("return JSON.stringify(window.__H2)") or "{}")
        except Exception:
            state = {}
        if state.get("tok"):
            log("Token do widget recebido, tamanho " + str(len(state["tok"])))
            return state["tok"]
        if state.get("err"):
            log("Erro do widget, " + str(state["err"])[:140])
            return None
    log("Tempo esgotado no widget")
    return None


def close_challenge(page, tab):
    """Fecha a aba usada para obter o captcha."""
    if page is None:
        return
    try:
        page.close_tabs(tabs=tab)
    except Exception:
        pass
