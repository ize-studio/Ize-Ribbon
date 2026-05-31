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


def has_hangul(text: str) -> bool:
    return any("HANGUL" in unicodedata.name(ch, "") for ch in text)


def is_hangul_char(ch: str) -> bool:
    return "HANGUL" in unicodedata.name(ch, "")


def font_for_text(text: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    config = load_config()
    font_key = "font_ko" if has_hangul(text) else "font_latin"
    path = project_path(config.get(font_key, ""))
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def font_for_char(ch: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    config = load_config()
    font_key = "font_ko" if is_hangul_char(ch) else "font_latin"
    path = project_path(config.get(font_key, ""))
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def mixed_textlength(draw: ImageDraw.ImageDraw, text: str, size: int) -> float:
    return sum(draw.textlength(ch, font=font_for_char(ch, size)) for ch in text)


def draw_mixed_text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, size: int, fill: int = 0) -> None:
    config = load_config()
    hangul_y_offset = int(config.get("hangul_y_offset", 2))
    x, y = xy
    for ch in text:
        font = font_for_char(ch, size)
        y_offset = hangul_y_offset if is_hangul_char(ch) else 0
        draw.text((x, y + y_offset), ch, fill=fill, font=font)
        x += draw.textlength(ch, font=font)


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
        return "[한]"
    return f"[{code}]"


def visible_body_lines(text: str, draw: ImageDraw.ImageDraw, width: int, max_lines: int, font_size: int | None = None) -> list[str]:
    config = load_config()
    size = font_size or int(config.get("body_font_size", 19))
    lines: list[str] = []
    for source_line in text.splitlines() or [""]:
        current = ""
        for ch in source_line:
            candidate = current + ch
            if mixed_textlength(draw, candidate, size) <= width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = ch
        lines.append(current)
    return lines[-max_lines:]


def render_image(overlay_lines: list[str] | None = None) -> Image.Image:
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

    text = read_text()
    title = f"{config.get('title', 'Ize Ribbon')} {language_badge(current_language())}"
    status_size = int(config.get("status_font_size", 12)) * scale
    body_size = int(config.get("body_font_size", 19)) * scale
    status_font = font_for_text(title, status_size)

    if invert_status:
        draw.rectangle((0, 0, canvas_width, top_h), fill=0)
        draw.rectangle((0, canvas_height - bottom_h, canvas_width, canvas_height), fill=0)

    status_fill = 255 if invert_status else 0
    separator_fill = 255 if invert_status else 0

    right_parts = []
    if not keyboard_connected():
        right_parts.append("[No KBD]")
    right_parts.append(battery_text())
    right = " ".join(right_parts)
    right_w = mixed_textlength(draw, right, status_size)
    left = fit_text(draw, title, status_font, canvas_width - margin * 3 - int(right_w))
    draw_mixed_text(draw, (margin, 2 * scale), left, status_size, fill=status_fill)
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
    label = note_label(current_document(), int(config.get("bottom_preview_chars", 16)))
    chars, words = counts(text)
    mode = config.get("count_mode", "chars")
    count_text = ""
    if mode == "chars":
        count_text = str(chars)
    elif mode == "words":
        count_text = str(words)
    label_font = font_for_text(label, status_size)
    count_font = font_for_text(count_text, status_size)
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


def send_image(image: Image.Image) -> None:
    try:
        lib_dir = os.environ.get("WAVESHARE_LIB_DIR")
        if lib_dir and lib_dir not in sys.path:
            sys.path.insert(0, lib_dir)
        from waveshare_epd import epd2in13_V4

        epd = epd2in13_V4.EPD()
        epd.init()
        epd.display(epd.getbuffer(image))
    except Exception:
        preview_path = ROOT / "last_render.png"
        image.save(preview_path)
        print(f"Display fallback wrote {preview_path}")


def show(overlay_lines: list[str] | None = None) -> None:
    send_image(render_image(overlay_lines))


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
