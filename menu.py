from dataclasses import dataclass

from config_store import load_config, save_config, update_activity
from documents import list_documents, new_document, set_current_document
from network_status import network_display_lines


MENU_ITEMS = ["New Doc", "Docs", "Network", "Auto Off", "Count", "Power Off"]
IDLE_OPTIONS = [("10m", 600), ("30m", 1800), ("60m", 3600)]
COUNT_OPTIONS = [("OFF", "off"), ("Words", "words"), ("Chars", "chars")]


@dataclass
class MenuState:
    mode: str = "writing"
    selected: int = 0
    doc_selected: int = 0
    option_confirmed: bool = False

    def open(self) -> None:
        self.mode = "menu"
        self.option_confirmed = False
        update_activity()

    def close(self) -> None:
        self.mode = "writing"
        self.option_confirmed = False
        update_activity()

    def handle(self, key: str) -> bool:
        update_activity()
        if self.mode == "menu":
            return self._handle_menu(key)
        if self.mode == "docs":
            return self._handle_docs(key)
        if self.mode == "network":
            return self._handle_network(key)
        if self.mode == "idle":
            return self._handle_idle(key)
        if self.mode == "count":
            return self._handle_count(key)
        return False

    def _handle_menu(self, key: str) -> bool:
        if key == "esc":
            self.close()
        elif key == "up":
            self.selected = (self.selected - 1) % len(MENU_ITEMS)
        elif key == "down":
            self.selected = (self.selected + 1) % len(MENU_ITEMS)
        elif key == "enter":
            item = MENU_ITEMS[self.selected]
            if item == "New Doc":
                self.mode = "newdoc"
            elif item == "Docs":
                self.mode = "docs"
                self.doc_selected = 0
            elif item == "Network":
                self.mode = "network"
            elif item == "Auto Off":
                self.mode = "idle"
                self.option_confirmed = False
            elif item == "Count":
                self.mode = "count"
                self.option_confirmed = False
            elif item == "Power Off":
                self.mode = "poweroff"
        return True

    def _handle_docs(self, key: str) -> bool:
        docs = list_documents()
        if key == "esc":
            self.mode = "menu"
        elif docs and key == "up":
            self.doc_selected = (self.doc_selected - 1) % len(docs)
        elif docs and key == "down":
            self.doc_selected = (self.doc_selected + 1) % len(docs)
        elif docs and key == "enter":
            set_current_document(docs[self.doc_selected])
            self.close()
        return True

    def _handle_network(self, key: str) -> bool:
        if key in ("esc", "enter"):
            self.mode = "menu"
        return True

    def _handle_idle(self, key: str) -> bool:
        config = load_config()
        current = int(config.get("idle_shutdown_seconds", 1800)) if config.get("idle_shutdown_enabled", True) else 0
        values = [value for _, value in IDLE_OPTIONS]
        index = values.index(current) if current in values else 0
        if key == "esc":
            self.mode = "menu"
        elif key in ("left", "right"):
            delta = -1 if key == "left" else 1
            value = values[(index + delta) % len(values)]
            config["idle_shutdown_enabled"] = value != 0
            config["idle_shutdown_seconds"] = value
            save_config(config)
            self.option_confirmed = False
        elif key == "enter":
            self.option_confirmed = True
        return True

    def _handle_count(self, key: str) -> bool:
        config = load_config()
        values = [value for _, value in COUNT_OPTIONS]
        current = config.get("count_mode", "chars")
        index = values.index(current) if current in values else 2
        if key == "esc":
            self.mode = "menu"
        elif key in ("left", "right"):
            delta = -1 if key == "left" else 1
            config["count_mode"] = values[(index + delta) % len(values)]
            save_config(config)
            self.option_confirmed = False
        elif key == "enter":
            self.option_confirmed = True
        return True

    def overlay_lines(self) -> list[str]:
        if self.mode == "menu":
            return [f"{'>' if i == self.selected else ' '} {self._menu_label(item)}" for i, item in enumerate(MENU_ITEMS)]
        if self.mode == "docs":
            docs = list_documents()
            start = max(0, min(self.doc_selected, max(0, len(docs) - 3)))
            lines = [f"Ize Docs {self.doc_selected + 1}/{max(len(docs), 1)}", ""]
            for i, path in enumerate(docs[start:start + 3], start):
                number = path.stem.replace("note", "")
                preview = path.read_text(encoding="utf-8").replace("\n", " ").strip()[:16]
                lines.append(f"{'>' if i == self.doc_selected else ' '} {number}:{preview}")
            return lines
        if self.mode == "network":
            return network_display_lines()
        if self.mode == "idle":
            config = load_config()
            current = int(config.get("idle_shutdown_seconds", 1800)) if config.get("idle_shutdown_enabled", True) else 0
            label = next((label for label, value in IDLE_OPTIONS if value == current), "30m")
            return [f"  {label}" if self.option_confirmed else f"< {label} >"]
        if self.mode == "count":
            config = load_config()
            current = config.get("count_mode", "chars")
            label = next((label for label, value in COUNT_OPTIONS if value == current), "Chars")
            return [f"  {label}" if self.option_confirmed else f"< {label} >"]
        return []

    def _menu_label(self, item: str) -> str:
        if item != "Auto Off":
            return item
        config = load_config()
        current = int(config.get("idle_shutdown_seconds", 1800)) if config.get("idle_shutdown_enabled", True) else 1800
        label = next((label for label, value in IDLE_OPTIONS if value == current), "30m")
        return f"Auto Off {label}"
