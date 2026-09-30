"""Where the six shooter blocks sit on a 200 dpi scoresheet page (fractions of page width/height)."""

from __future__ import annotations

from PIL import Image

TOP = 0.105
BOTTOM = 0.905
ROWS = 3
COLUMN_X = ((0.03, 0.495), (0.505, 0.97))
# The handwritten "Tot" column and the boxed Event Total sit at the right edge of a block.
TOT_X = (0.86, 1.0)
TOT_Y = (0.15, 1.0)
TOT_UPSCALE = 2
BLOCKS_PER_PAGE = ROWS * len(COLUMN_X)


def crop_blocks(page: Image.Image) -> list[Image.Image]:
    """The six blocks, numbered left to right then top to bottom (2 columns x 3 rows)."""
    width, height = page.size
    top, bottom = int(height * TOP), int(height * BOTTOM)
    row_height = (bottom - top) / ROWS
    crops: list[Image.Image] = []
    for row in range(ROWS):
        for x0, x1 in COLUMN_X:
            box = (int(width * x0), int(top + row * row_height), int(width * x1), int(top + (row + 1) * row_height))
            crops.append(page.crop(box))
    return crops


def tot_crop(block: Image.Image) -> Image.Image:
    """Only the Tot column, upscaled: the model reads digits far better without the marks beside them."""
    width, height = block.size
    box = (int(width * TOT_X[0]), int(height * TOT_Y[0]), int(width * TOT_X[1]), int(height * TOT_Y[1]))
    part = block.crop(box)
    return part.resize((part.width * TOT_UPSCALE, part.height * TOT_UPSCALE), Image.Resampling.LANCZOS)
