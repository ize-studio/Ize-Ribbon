from pathlib import Path
import os
import sys
import unicodedata

from PIL import Image, ImageDraw, ImageFont

from battery import battery_text
from config_store import ROOT, load_config, project_path
from documents import counts, current_document, note_label, read_text
from keyboard_status import keyboard_connected
from language import current_language


EPD_WIDTH = 250
EPD_HEIGHT = 122
_EPD = None
_BASE_READY = False
_FONT_CACHE = {}
_FONT_PATH_CACHE = {}
_CHAR_WIDTH_CACHE = {}
_HANGUL_Y_OFFSET = None
_STATUS_CACHE = {
    "title": "Ize Ribbon [EN]",
    "right": "",
    "label": "",
    "count": "",
}


def font_path(font_key: str):
    if font_key not in _FONT_PATH_CACHE:
        config = load_config()
        _FONT_PATH_CACHE[font_key] = project_path(config.get(font_key, ""))
    return _FONT_PATH_CACHE[font_key]


def has_hangul(text: str) -> bool:
    return any("HANGUL" in unicodedata.name(ch, "") for ch in text)


def is_hangul_char(ch: str) -> bool:
    return "HANGUL" in unicodedata.name(ch, "")


def font_for_text(text: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_key = "font_ko" if has_hangul(text) else "font_latin"
    path = font_path(font_key)
    cache_key = (str(path), size)
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]
    try:
        font = ImageFont.truetype(str(path), size)
    except OSError:
        font = ImageFont.load_default()
    _FONT_CACHE[cache_key] = font
    return font


def font_for_char(ch: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_key = "font_ko" if is_hangul_char(ch) else "font_latin"
    path = font_path(font_key)
    cache_key = (str(path), size)
    if cache_key in _FONT_CACHE:
        return _FONT_CACHE[cache_key]
    try:
        font = ImageFont.truetype(str(path), size)
    except OSError:
        font = ImageFont.load_default()
    _FONT_CACHE[cache_key] = font
    return font


def char_width(draw: ImageDraw.ImageDraw, ch: str, size: int) -> float:
    font = font_for_char(ch, size)
    cache_key = (ch, size, id(font))
    if cache_key not in _CHAR_WIDTH_CACHE:
        _CHAR_WIDTH_CACHE[cache_key] = draw.textlength(ch, font=font)
    return _CHAR_WIDTH_CACHE[cache_key]


def mixed_textlength(draw: ImageDraw.ImageDraw, text: str, size: int) -> float:
    return sum(char_width(draw, ch, size) for ch in text)


def draw_mixed_text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, size: int, fill: int = 0) -> None:
    global _HANGUL_Y_OFFSET
    if _HANGUL_Y_OFFSET is None:
        _HANGUL_Y_OFFSET = int(load_config().get("hangul_y_offset", 2))
    x, y = xy
    for ch in text:
        font = font_for_char(ch, size)
        y_offset = _HANGUL_Y_OFFSET if is_hangul_char(ch) else 0
        draw.text((x, y + y_offset), ch, fill=fill, font=font)
        x += char_width(draw, ch, size)


def fit_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    result = text
    while result and draw.textlength(result + "...", font=font) > max_width:
        result = result[:-1]
    return result + "..." if result else ""


def fit_mixed_text_short_ellipsis(draw: ImageDraw.ImageDraw, text: str, size: int, max_width: int) -> str:
    if mixed_textlength(draw, text, size) <= max_width:
        return text
    result = text
    suffix = ".."
    while result and mixed_textlength(draw, result + suffix, size) > max_width:
        result = result[:-1]
    return result + suffix if result else ""


def language_badge(code: str) -> str:
    if code == "KO":
        return "[KO]"
    return f"[{code}]"


def visible_body_lines(text: str, draw: ImageDraw.ImageDraw, width: int, max_lines: int, font_size: int | None = None) -> list[str]:
    config = load_config()
    size = font_size or int(config.get("body_font_size", 19))
    text = text[-int(config.get("display_tail_chars", 320)):]
    lines: list[str] = []
    for source_line in text.splitlines() or [""]:
        current = ""
        current_width = 0.0
        for ch in source_line:
            ch_width = char_width(draw, ch, size)
            if current_width + ch_width <= width:
                current += ch
                current_width += ch_width
            else:
                if current:
                    lines.append(current)
                current = ch
                current_width = ch_width
        lines.append(current)
    return lines[-max_lines:]


def render_image(overlay_lines: list[str] | None = None, text_override: str | None = None, lightweight: bool = False) -> Image.Image:
    config = load_config()
    width = int(config.get("width", EPD_WIDTH))
    height = int(config.get("height", EPD_HEIGHT))
    scale = max(1, int(config.get("render_scale", 1)))
    top_h = int(config.get("top_bar_height", 18)) * scale
    bottom_h = int(config.get("bottom_bar_height", 18)) * scale
    margin = int(config.get("margin", 6)) * scale
    threshold = int(config.get("threshold", 155))
    invert_status = bool(config.get("invert_status_bars", True))
    canvas_width = width * scale
    canvas_height = height * scale

    image = Image.new("L", (canvas_width, canvas_height), 255)
    draw = ImageDraw.Draw(image)

    text = read_text() if text_override is None else text_override
    status_size = int(config.get("status_font_size", 12)) * scale
    body_size = int(config.get("body_font_size", 19)) * scale

    if invert_status:
        draw.rectangle((0, 0, canvas_width, top_h), fill=0)
        draw.rectangle((0, canvas_height - bottom_h, canvas_width, canvas_height), fill=0)

    status_fill = 255 if invert_status else 0
    separator_fill = 255 if invert_status else 0

    if lightweight:
        title = _STATUS_CACHE["title"]
        right = _STATUS_CACHE["right"]
    else:
        title = f"{config.get('title', 'Ize Ribbon')} {language_badge(current_language())}"
        right_parts = []
        if not keyboard_connected():
            right_parts.append("[No KBD]")
        right_parts.append(battery_text())
        right = " ".join(right_parts)
        _STATUS_CACHE["title"] = title
        _STATUS_CACHE["right"] = right
    status_font = font_for_text(title, status_size)
    right_w = mixed_textlength(draw, right, status_size)
    left = fit_text(draw, title, status_font, canvas_width - margin * 3 - int(right_w))
    draw_mixed_text(draw, (margin, 2 * scale), left, status_size, fill=status_fill)
    if right:
        draw_mixed_text(draw, (canvas_width - margin - right_w, 2 * scale), right, status_size, fill=status_fill)
    if not invert_status:
        draw.line((0, top_h, canvas_width, top_h), fill=separator_fill, width=scale)

    body_top = top_h + 3 * scale
    body_bottom = canvas_height - bottom_h - 2 * scale
    line_gap = int(config.get("line_gap", 20)) * scale
    max_lines = max(1, (body_bottom - body_top) // line_gap)
    max_lines = min(max_lines, int(config.get("body_visible_lines", 3)))
    body_width = canvas_width - margin * 2
    lines = overlay_lines if overlay_lines is not None else visible_body_lines(text, draw, body_width, max_lines, body_size)
    lines_height = line_gap * max(0, len(lines) - 1) + body_size
    y = body_top + max(0, (body_bottom - body_top - lines_height) // 2)
    for line in lines:
        draw_mixed_text(draw, (margin, y), line, body_size)
        y += line_gap

    if not invert_status:
        draw.line((0, canvas_height - bottom_h, canvas_width, canvas_height - bottom_h), fill=separator_fill, width=scale)
    if lightweight:
        label = _STATUS_CACHE["label"]
        count_text = _STATUS_CACHE["count"]
    else:
        label = note_label(current_document(), int(config.get("bottom_preview_chars", 16)))
        chars, words = counts(text)
        mode = config.get("count_mode", "chars")
        count_text = ""
        if mode == "chars":
            count_text = str(chars)
        elif mode == "words":
            count_text = str(words)
        _STATUS_CACHE["label"] = label
        _STATUS_CACHE["count"] = count_text
    max_label_width = canvas_width - margin * 3
    if count_text:
        max_label_width -= int(mixed_textlength(draw, count_text, status_size))
    label = fit_mixed_text_short_ellipsis(draw, label, status_size, max_label_width)
    draw_mixed_text(draw, (margin, canvas_height - bottom_h + 3 * scale), label, status_size, fill=status_fill)
    if count_text:
        cw = mixed_textlength(draw, count_text, status_size)
        draw_mixed_text(draw, (canvas_width - margin - cw, canvas_height - bottom_h + 3 * scale), count_text, status_size, fill=status_fill)

    if scale > 1:
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    return image.point(lambda p: 0 if p < threshold else 255, "1")


def epd_device():
    global _EPD
    if _EPD is not None:
        return _EPD
    lib_dir = os.environ.get("WAVESHARE_LIB_DIR")
    if lib_dir and lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)
    from waveshare_epd import epd2in13_V4

    _EPD = epd2in13_V4.EPD()
    _EPD.init()
    return _EPD


def send_image(image: Image.Image, partial: bool = False) -> None:
    global _BASE_READY
    try:
        rotation = int(load_config().get("display_rotation", 0)) % 360
        if rotation == 180:
            image = image.rotate(180)
        epd = epd_device()
        buffer = epd.getbuffer(image)
        if _BASE_READY and hasattr(epd, "displayPartial"):
            epd.displayPartial(buffer)
        elif not _BASE_READY and hasattr(epd, "displayPartBaseImage"):
            epd.displayPartBaseImage(buffer)
            _BASE_READY = True
        elif hasattr(epd, "display_fast"):
            epd.display_fast(buffer)
            _BASE_READY = True
        else:
            epd.display(buffer)
            _BASE_READY = True
    except Exception:
        preview_path = ROOT / "last_render.png"
        image.save(preview_path)
        print(f"Display fallback wrote {preview_path}")


def show(
    overlay_lines: list[str] | None = None,
    partial: bool = False,
    text_override: str | None = None,
    lightweight: bool = False,
) -> None:
    send_image(render_image(overlay_lines, text_override=text_override, lightweight=lightweight), partial=partial)


def show_message(message: str | list[str]) -> None:
    config = load_config()
    width = int(config.get("width", EPD_WIDTH))
    height = int(config.get("height", EPD_HEIGHT))
    scale = max(1, int(config.get("render_scale", 1)))
    threshold = int(config.get("threshold", 155))
    canvas_width = width * scale
    canvas_height = height * scale
    image = Image.new("L", (canvas_width, canvas_height), 255)
    draw = ImageDraw.Draw(image)
    lines = [message] if isinstance(message, str) else message
    fonts = []
    sizes = []
    for index, line in enumerate(lines):
        size = int(config.get("body_font_size", 19)) if index == 0 else int(config.get("status_font_size", 12))
        size *= scale
        font = font_for_text(line, size)
        bbox = draw.textbbox((0, 0), line, font=font)
        fonts.append(font)
        sizes.append((draw.textlength(line, font=font), bbox[3] - bbox[1]))
    line_gap = 8 * scale
    total_height = sum(h for _, h in sizes) + line_gap * max(0, len(lines) - 1)
    y = (canvas_height - total_height) / 2
    for line, font, (text_width, text_height) in zip(lines, fonts, sizes):
        draw.text(((canvas_width - text_width) / 2, y), line, fill=0, font=font)
        y += text_height + line_gap
    if scale > 1:
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    send_image(image.point(lambda p: 0 if p < threshold else 255, "1"))
