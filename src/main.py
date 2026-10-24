import importlib.util
import logging
import sys
import time

from core import browser
from core.config import ROOT, load_config
from core.flow import run
from utils import runtime
from utils.runtime import require_direct_connection


def main():
    try:
        if sys.argv[1:]:
            raise ValueError("Execute src/main.py sem parâmetros")
        if runtime.require_elevated():
            runtime.ELEVATION_RELAUNCHED = True
            return 0
    except (ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 2

    output_dir = ROOT / "out"
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(output_dir / "login.log", mode="w", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    started = time.monotonic()
    logging.info("Início do login")
    result = 9
    try:
        require_direct_connection()
        config = load_config()
        if not config["RIOT_USER"] or not config["RIOT_PASS"]:
            raise ValueError("Preencha RIOT_USER e RIOT_PASS no .env")
        if not config["CLIENTE_EXE"] or not (ROOT / config["CLIENTE_EXE"]).is_file():
            raise ValueError("CLIENTE_EXE inválido no .env")
        if importlib.util.find_spec("DrissionPage") is None:
            raise ValueError("Instale as dependências de requirements.txt")
        config["CHROME_EXE"] = browser._find_browser(config["CHROME_EXE"], logging.info)
        logging.info("Verificações concluídas: administrador, conexão direta, .env UTF-8 e executáveis válidos")
        result = run(config, logging.info)
    except UnicodeError:
        logging.error("O .env precisa estar salvo em UTF-8 (BOM é aceito)")
        result = 2
    except (ValueError, RuntimeError) as error:
        logging.error(str(error))
        result = 2
    except KeyboardInterrupt:
        logging.warning("Execução interrompida pelo usuário")
        result = 130
    except Exception:
        logging.exception("Falha inesperada")
        result = 9
    elapsed = time.monotonic() - started
    if result == 0:
        logging.info("Concluído: Riot Client autenticado. Tempo total: %.2f s", elapsed)
    else:
        logging.error("Execução encerrada com código %s. Tempo total: %.2f s", result, elapsed)
    return result


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    exit_code = main()
    if not runtime.ELEVATION_RELAUNCHED:
        try:
            input("\nPressione Enter para fechar... ")
        except EOFError:
            pass
    sys.exit(exit_code)
