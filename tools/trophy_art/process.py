"""Candidate PNG → circular medallion WebP: centred square crop, anti-aliased circular alpha."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw

SUPERSAMPLE = 4


def square_crop(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    return image.crop((left, top, left + side, top + side))


def circular_mask(size: int) -> Image.Image:
    big = size * SUPERSAMPLE
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    return mask.resize((size, size), Image.Resampling.LANCZOS)


def medallion(png: bytes, size: int) -> bytes:
    with Image.open(BytesIO(png)) as source:
        image = square_crop(source.convert("RGBA")).resize((size, size), Image.Resampling.LANCZOS)
    image.putalpha(circular_mask(size))
    out = BytesIO()
    image.save(out, format="WEBP", quality=90, method=6)
    return out.getvalue()
