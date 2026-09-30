from io import BytesIO

from PIL import Image

from process import medallion


def to_png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def test_medallion_is_a_square_webp_with_transparent_corners():
    out = Image.open(BytesIO(medallion(to_png(Image.new("RGB", (300, 200), (200, 60, 40))), 256)))
    assert (out.format, out.size, out.mode) == ("WEBP", (256, 256), "RGBA")
    assert out.getpixel((0, 0))[3] == 0
    assert out.getpixel((128, 128))[3] == 255


def test_medallion_crops_the_centre_square():
    image = Image.new("RGB", (300, 200), (255, 0, 0))
    image.paste((0, 0, 255), (50, 0, 250, 200))  # the centred 200x200 square is blue, the margins red
    red, _, blue, alpha = Image.open(BytesIO(medallion(to_png(image), 128))).convert("RGBA").getpixel((16, 64))
    assert alpha == 255
    assert blue > 200 and red < 60


def test_small_size_is_128():
    assert Image.open(BytesIO(medallion(to_png(Image.new("RGB", (64, 64))), 128))).size == (128, 128)
