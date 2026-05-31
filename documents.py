from pathlib import Path
import re

from config_store import ROOT, load_config, project_path, save_config, update_activity


NOTE_RE = re.compile(r"^note(\d{4})\.txt$")


def docs_dir() -> Path:
    path = ROOT / "docs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_documents() -> list[Path]:
    return sorted(
        [p for p in docs_dir().glob("note*.txt") if NOTE_RE.match(p.name)],
        key=lambda p: p.name,
    )


def ensure_initial_document() -> Path:
    docs = list_documents()
    if docs:
        return docs[0]
    path = docs_dir() / "note0001.txt"
    path.write_text("", encoding="utf-8")
    return path


def current_document() -> Path:
    config = load_config()
    path = project_path(config.get("document", "docs/note0001.txt"))
    if not path.exists():
        path = ensure_initial_document()
        set_current_document(path)
    return path


def set_current_document(path: Path) -> None:
    config = load_config()
    config["document"] = str(path.relative_to(ROOT))
    save_config(config)
    update_activity()


def new_document() -> Path:
    max_number = 0
    for path in list_documents():
        match = NOTE_RE.match(path.name)
        if match:
            max_number = max(max_number, int(match.group(1)))
    path = docs_dir() / f"note{max_number + 1:04d}.txt"
    path.write_text("", encoding="utf-8")
    set_current_document(path)
    return path


def read_text(path: Path | None = None) -> str:
    path = path or current_document()
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(text: str, path: Path | None = None) -> None:
    path = path or current_document()
    path.write_text(text, encoding="utf-8")
    update_activity()


def append_text(text: str) -> None:
    path = current_document()
    with path.open("a", encoding="utf-8") as f:
        f.write(text)
    update_activity()


def backspace() -> None:
    text = read_text()
    if text:
        write_text(text[:-1])


def note_label(path: Path, preview_chars: int = 5) -> str:
    match = NOTE_RE.match(path.name)
    number = match.group(1) if match else path.stem
    preview = read_text(path).replace("\n", " ").strip()[:preview_chars]
    return f"{number}:{preview}"


def counts(text: str) -> tuple[int, int]:
    chars = len(text)
    words = len([part for part in re.split(r"\s+", text.strip()) if part])
    return chars, words


def preview(text: str, limit: int) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= limit:
        return one_line
    return one_line[:limit] + "..."
