"""The Sunday Clays mark (D9): a clay target in three-quarter view on a green rounded square."""

from typing import Final

from PIL import Image, ImageDraw

GREEN: Final = "#1A4D2E"
DOME: Final = "#C76D3F"
RIM: Final = "#9E5530"
HIGHLIGHT: Final = "#E8A77A"
_SUPERSAMPLE: Final = 4


def draw_mark(size: int, *, background: bool = True) -> Image.Image:
    """The mark as an RGBA square of ``size`` px, drawn 4x larger and scaled down (smooth edges)."""
    s = size * _SUPERSAMPLE
    image = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if background:
        draw.rounded_rectangle((0, 0, s - 1, s - 1), radius=s // 5, fill=GREEN)
    width, height = s * 0.70, s * 0.30
    left, right = (s - width) / 2, (s + width) / 2
    draw.ellipse((left, s * 0.47, right, s * 0.47 + height), fill=RIM)  # the rim, below
    dome_top = s * 0.38
    draw.ellipse((left, dome_top, right, dome_top + height), fill=DOME)  # the dome
    inset_x, inset_y = width * 0.22, height * 0.22
    draw.ellipse(
        (left + inset_x, dome_top + inset_y, right - inset_x, dome_top + height - inset_y),
        outline=HIGHLIGHT,
        width=max(1, s // 40),
    )
    return image.resize((size, size), Image.Resampling.LANCZOS)
