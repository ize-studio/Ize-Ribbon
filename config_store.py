import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict[str, Any]) -> None:
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(CONFIG_PATH)


def project_path(relative_or_absolute: str) -> Path:
    path = Path(relative_or_absolute)
    if path.is_absolute():
        return path
    return ROOT / path


def update_activity() -> None:
    config = load_config()
    path = Path(config.get("activity_file", "/run/ize-ribbon/activity"))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(__import__("time").time()), encoding="ascii")
    except OSError:
        pass
