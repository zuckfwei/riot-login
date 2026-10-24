"""Navegador usado para abrir o login da Riot e resolver o hCaptcha."""

import ctypes
from ctypes import wintypes
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


def open_browser(browser_executable, profile_dir, log):
    """Abre o navegador configurado com o perfil local do programa."""
    from DrissionPage import ChromiumOptions, ChromiumPage

    browser_executable = _find_browser(browser_executable, log)

    options = ChromiumOptions()
    options.set_browser_path(browser_executable)
    options.set_local_port(9333)
    options.set_user_data_path(str(profile_dir))
    options.set_argument("--start-maximized")
    options.set_argument("--no-first-run")
    options.set_argument("--no-default-browser-check")

    page = ChromiumPage(addr_or_opts=options)
    page.set.window.max()
    return page


def _keep_window_visible(page, tab, log):
    """Restaura, maximiza e mantém no topo a janela do Chrome desta guia."""
    if os.name != "nt":
        return

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]

    process_id = page.browser.process_id
    title = str(tab.title or "").casefold()
    windows = []

    @callback_type
    def collect_window(handle, _):
        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(window_pid))
        if window_pid.value == process_id and user32.IsWindowVisible(handle):
            length = user32.GetWindowTextLengthW(handle)
            text = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(handle, text, len(text))
            windows.append((handle, text.value))
        return True

    user32.EnumWindows(collect_window, 0)
    if not windows:
        log("Não encontrei a janela do Chrome para trazê-la ao topo")
        return

    handle = next(
        (window for window, caption in windows if title and title in caption.casefold()),
        windows[0][0],
    )
    page.activate_tab(tab.tab_id)
    user32.ShowWindow(handle, 9)
    page.set.window.max()
    user32.SetWindowPos(handle, ctypes.c_void_p(-1), 0, 0, 0, 0, 0x43)
    user32.SetForegroundWindow(handle)
    log("Chrome maximizado e mantido no topo")


def open_login_page(browser_executable, profile_dir, log):
    """Prepara a página oficial enquanto o serviço prepara a sessão."""
    page = open_browser(browser_executable, profile_dir, log)
    tab = page.get_tab()
    tab.get("https://www.riotgames.com/en")
    _keep_window_visible(page, tab, log)
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
    log("Abrindo a página oficial de autenticação")
    if isinstance(action, str) and action.startswith("href:"):
        tab.run_js("location.href = " + json.dumps(action[5:]) + ";")

    deadline = time.time() + 45
    while time.time() < deadline:
        if "authenticate.riotgames.com" in str(tab.url or ""):
            break
        time.sleep(1)

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
    if not loaded:
        raise RuntimeError("hcaptcha.js não carregou")
    log("Página de autenticação e hCaptcha prontos")
    _keep_window_visible(page, tab, log)
    return page, tab


def render_challenge(tab, site_key):
    """Cria o widget somente depois de obter o desafio da sessão atual."""
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
    tab.run_js(render_widget)


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
    log("Aguardando o captcha manual na janela do navegador")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            state = json.loads(tab.run_js("return JSON.stringify(window.__H2)") or "{}")
        except Exception:
            state = {}
        if state.get("tok"):
            log("Captcha resolvido; enviando a resposta à API")
            return state["tok"]
        if state.get("err"):
            log("Erro do widget, " + str(state["err"])[:140])
            return None
        time.sleep(0.2)
    log("Tempo esgotado no widget")
    return None


def close_challenge(page, tab):
    """Limpa o captcha na mesma guia e deixa uma única janela aberta."""
    if page is None:
        return
    try:
        tab.get("about:blank")
    except Exception:
        pass
