"""The 1200x630 PNG card (Plan 19 §3.1.4, D8)."""

import io
import struct
from datetime import date

from PIL import Image, ImageDraw

from sunday_clays.domain.round_type import RoundType
from sunday_clays.og import render
from sunday_clays.og.facts import GENERIC, PreviewFacts

SUNDAY = PreviewFacts("sunday", date(2026, 9, 27), 23, RoundType.SPORTING)


def _chunks(png: bytes) -> list[bytes]:
    out, pos = [], 8
    while pos < len(png):
        (length,) = struct.unpack(">I", png[pos : pos + 4])
        out.append(png[pos + 4 : pos + 8])
        pos += 12 + length
    return out


def test_same_facts_same_bytes_and_no_text_chunks() -> None:
    first, second = render.render_card(SUNDAY), render.render_card(SUNDAY)
    assert first == second
    chunks = _chunks(first)
    assert b"tEXt" not in chunks
    assert b"iTXt" not in chunks
    assert b"zTXt" not in chunks
    image = Image.open(io.BytesIO(first))
    assert image.size == (1200, 630)


def test_different_facts_different_bytes() -> None:
    assert render.render_card(SUNDAY) != render.render_card(GENERIC)


def test_background_pixel_is_the_club_green() -> None:
    image = Image.open(io.BytesIO(render.render_card(GENERIC))).convert("RGB")
    assert image.getpixel((1190, 10)) == (0x1A, 0x4D, 0x2E)


def test_fit_shrinks_then_truncates_a_long_label() -> None:
    draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    short_font, short = render.fit(draw, "3-Bird Shoot", render.MEDIUM, 52)
    assert short == "3-Bird Shoot"
    assert short_font.size == 52
    long_label = "W" * 60
    font, text = render.fit(draw, long_label, render.MEDIUM, 52)
    assert font.size == render.MIN_SIZE
    assert text.endswith("…")
    assert len(text) < 61
    assert draw.textlength(text, font=font) <= render.MAX_TEXT_WIDTH


def test_a_60_character_label_renders() -> None:
    label = "A very long special shoot label that runs past the card edge"
    assert len(label) == 60
    facts = PreviewFacts("special", date(2026, 9, 20), 40, RoundType.SPORTING, label)
    assert Image.open(io.BytesIO(render.render_card(facts))).size == (1200, 630)
