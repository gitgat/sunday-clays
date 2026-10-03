"""The 1200x630 preview card (§3.1.4): fixed fonts, colours and coordinates, no metadata (D8)."""

import functools
import io
from pathlib import Path
from typing import Final

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from sunday_clays.analytics.cache import _database_name, read_data_version
from sunday_clays.og.facts import PreviewFacts
from sunday_clays.og.html import image_lines
from sunday_clays.og.logo import GREEN, draw_mark

WIDTH: Final = 1200
HEIGHT: Final = 630
CREAM: Final = "#FEFBF6"
MINT: Final = "#D4E7DD"
CLAY_LIGHT: Final = "#E8A77A"
FONTS: Final = Path(__file__).parent / "fonts"
REGULAR: Final = FONTS / "Roboto-Regular.ttf"
MEDIUM: Final = FONTS / "Roboto-Medium.ttf"
MAX_TEXT_WIDTH: Final = 1040
MIN_SIZE: Final = 32
ELLIPSIS: Final = "…"


def _font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def fit(
    draw: ImageDraw.ImageDraw, text: str, path: Path, size: int
) -> tuple[ImageFont.FreeTypeFont, str]:
    """Shrink in 2 px steps down to 32 px until ``text`` fits 1040 px, then truncate with …"""
    while size >= MIN_SIZE:
        font = _font(path, size)
        if draw.textlength(text, font=font) <= MAX_TEXT_WIDTH:
            return font, text
        size -= 2
    font = _font(path, MIN_SIZE)
    while text and draw.textlength(text + ELLIPSIS, font=font) > MAX_TEXT_WIDTH:
        text = text[:-1]
    return font, text.rstrip() + ELLIPSIS


def render_card(facts: PreviewFacts) -> bytes:
    image = Image.new("RGB", (WIDTH, HEIGHT), GREEN)
    mark = draw_mark(160)
    image.paste(mark, (80, 80), mark)
    draw = ImageDraw.Draw(image)
    draw.text((80, 290), "Sunday Clays", font=_font(MEDIUM, 72), fill=CREAM)
    draw.text((80, 380), "Tri-County Gun Club", font=_font(REGULAR, 40), fill=MINT)
    lines = image_lines(facts)
    if lines is not None:
        font_a, line_a = fit(draw, lines[0], MEDIUM, 52)
        draw.text((80, 450), line_a, font=font_a, fill=CLAY_LIGHT)
        font_b, line_b = fit(draw, lines[1], REGULAR, 40)
        draw.text((80, 520), line_b, font=font_b, fill=CREAM)
    footer = _font(REGULAR, 28)
    draw.text((1120, 590), "sundayclays.claysmasher.com", font=footer, fill=MINT, anchor="rs")
    out = io.BytesIO()
    image.save(out, format="PNG")  # no pnginfo: no tEXt/iTXt chunks, same facts -> same bytes
    return out.getvalue()


CARD_CACHE_SIZE: Final = 64


@functools.lru_cache(maxsize=CARD_CACHE_SIZE)
def _cached_card(facts: PreviewFacts, database: str, data_version: int) -> bytes:
    return render_card(facts)


def card_png(session: Session, facts: PreviewFacts) -> bytes:
    """The card, in its own LRU of 64 per process, keyed by (facts, database, data_version).

    Deliberately not ``cached_by_data_version``: these routes are public, so their entries must
    never share (and evict from) the 256-entry analytics memo. Nothing is written to disk.
    """
    return _cached_card(facts, _database_name(session), read_data_version(session))
