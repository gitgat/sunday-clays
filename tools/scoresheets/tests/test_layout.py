from PIL import Image, ImageDraw

import layout


def synthetic_page() -> Image.Image:
    """A 1700x2200 page with each block painted a distinct grey and a marker in its Tot column."""
    page = Image.new("RGB", (1700, 2200), "white")
    draw = ImageDraw.Draw(page)
    top, bottom = int(2200 * layout.TOP), int(2200 * layout.BOTTOM)
    row_h = (bottom - top) / layout.ROWS
    for index in range(layout.BLOCKS_PER_PAGE):
        row, col = divmod(index, 2)
        x0, x1 = (int(1700 * f) for f in layout.COLUMN_X[col])
        y0 = int(top + row * row_h)
        draw.rectangle((x0, y0, x1 - 1, int(y0 + row_h) - 1), fill=(index * 30, index * 30, index * 30))
    return page


def test_six_blocks_in_reading_order():
    blocks = layout.crop_blocks(synthetic_page())
    assert len(blocks) == 6
    for index, block in enumerate(blocks):
        assert block.getpixel((block.width // 2, block.height // 2)) == (index * 30,) * 3
    assert abs(blocks[0].width - blocks[5].width) <= 2 and abs(blocks[0].height - blocks[5].height) <= 2
    assert 0.44 < blocks[0].width / 1700 < 0.47


def test_tot_crop_is_the_right_edge_upscaled():
    block = Image.new("RGB", (800, 600), "white")
    ImageDraw.Draw(block).rectangle((0, 0, 600, 599), fill="black")  # everything left of x=0.75 is black
    tot = layout.tot_crop(block)
    assert tot.size == ((800 - int(800 * 0.86)) * 2, (600 - int(600 * 0.15)) * 2)
    assert tot.getpixel((tot.width // 2, tot.height // 2)) == (255, 255, 255)
