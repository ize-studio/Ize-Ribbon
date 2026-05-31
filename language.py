from config_store import load_config, save_config, update_activity


def selected_codes() -> list[str]:
    config = load_config()
    codes = list(config.get("selected_languages", ["EN", "KO"]))
    normalized = ["EN"]
    for code in codes:
        code = str(code).upper()
        if code != "EN" and code not in normalized:
            normalized.append(code)
    return normalized[:5]


def current_language() -> str:
    config = load_config()
    codes = selected_codes()
    index = int(config.get("input_language_index", 0)) % len(codes)
    return codes[index]


def cycle_language() -> str:
    config = load_config()
    codes = selected_codes()
    index = (int(config.get("input_language_index", 0)) + 1) % len(codes)
    config["selected_languages"] = codes
    config["input_language_index"] = index
    config["input_mode"] = codes[index]
    save_config(config)
    update_activity()
    return codes[index]


def set_selected_languages(codes: list[str]) -> None:
    normalized = ["EN"]
    for code in codes:
        code = str(code).upper()
        if code != "EN" and code not in normalized:
            normalized.append(code)
    config = load_config()
    config["selected_languages"] = normalized[:5]
    config["input_language_index"] = 0
    config["input_mode"] = "EN"
    save_config(config)
    update_activity()
