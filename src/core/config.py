import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_config():
    """lê o .env para setar paths e creds."""
    values = {
        "RIOT_USER": "",
        "RIOT_PASS": "",
        "CLIENTE_EXE": "",
        "CHROME_EXE": "",
    }
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            key = key.strip()
            if separator and key in values:
                values[key] = value.strip()

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    values["output_dir"] = ROOT / "out"
    values["profile_dir"] = ROOT / "browser-profile"
    values["yaml_path"] = (
        Path(local_app_data)
        / "Riot Games"
        / "Riot Client"
        / "Data"
        / "RiotGamesPrivateSettings.yaml"
    )
    return values
