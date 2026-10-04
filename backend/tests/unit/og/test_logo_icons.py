"""One logo drawn in code (D9) and the PWA icons written from it."""

from pathlib import Path

import pytest
from PIL import Image

from sunday_clays.og import icons, logo


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    return tuple(int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def test_mark_colours_and_rounded_corner() -> None:
    mark = logo.draw_mark(160)
    assert mark.size == (160, 160)
    assert mark.mode == "RGBA"
    assert mark.getpixel((1, 1))[3] == 0  # rounded corner: transparent
    assert mark.getpixel((4, 80))[:3] == _rgb(logo.GREEN)
    r, g, b, _ = mark.getpixel((80, 85))  # the dome's centre, well inside the highlight ring
    assert (r, g, b) == _rgb(logo.DOME)


def test_mark_without_background_is_transparent_at_the_edge() -> None:
    assert logo.draw_mark(160, background=False).getpixel((4, 80))[3] == 0


def test_write_icons_writes_every_size(tmp_path: Path) -> None:
    written = icons.write_icons(tmp_path)
    assert sorted(p.name for p in written) == sorted(icons.ICONS)
    for name, (size, maskable) in icons.ICONS.items():
        with Image.open(tmp_path / name) as image:
            assert image.size == (size, size)
            if maskable:  # full bleed: the corner is the club green, not transparent
                assert image.convert("RGB").getpixel((0, 0)) == _rgb(logo.GREEN)


def test_main_writes_into_the_given_folder(tmp_path: Path) -> None:
    assert icons.main([str(tmp_path / "out")]) == 0
    assert (tmp_path / "out" / "icon-512.png").is_file()


def test_main_without_a_folder_is_a_usage_error() -> None:
    with pytest.raises(SystemExit):
        icons.main([])
