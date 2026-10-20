import importlib.util
import logging
import sys
from pathlib import Path

from core.config import load_config
from core.flow import run


def main():
    config = load_config()
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=output_dir / "login.log",
        level=logging.INFO,
        format="%(message)s",
        encoding="utf-8",
    )
    log = logging.info

    if importlib.util.find_spec("DrissionPage") is None:
        message = (
            "DrissionPage não está instalado."
        )
        log(message)
        print(message, file=sys.stderr)
        return 9

    try:
        result = run(config, log)
    except RuntimeError as error:
        logging.exception("Falha de execução")
        print(str(error), file=sys.stderr)
        result = 9
    except Exception as error:
        logging.exception("Falha inesperada")
        print("Falha inesperada: " + str(error), file=sys.stderr)
        result = 9

    log("exit=" + str(result))
    return result


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
