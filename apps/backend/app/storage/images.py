"""Validate and sanitize uploaded images.

Every image is decoded and re-encoded as JPEG: this strips EXIF/GPS and any
non-image payload, normalizes orientation and bounds the resolution.
"""
import io

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_PIXELS = 40_000_000  # decompression-bomb guard

Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class InvalidImage(ValueError):
    pass


def sanitize_image(data: bytes, filename: str | None, content_type: str | None, max_side: int) -> bytes:
    ext = (filename or "").rsplit(".", 1)[-1].lower() if filename and "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidImage("فرمت فایل مجاز نیست. فقط JPG، PNG یا WEBP.")
    if content_type not in ALLOWED_FORMATS.values():
        raise InvalidImage("نوع فایل مجاز نیست. فقط JPG، PNG یا WEBP.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = probe.format
            probe.verify()
        if fmt not in ALLOWED_FORMATS:
            raise InvalidImage("محتوای فایل تصویر معتبر نیست.")
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode not in ("RGB", "L"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                rgba = img.convert("RGBA")
                background.paste(rgba, mask=rgba.split()[-1])
                img = background
            else:
                img = img.convert("RGB")
            img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            # No exif= argument => no metadata is written
            img.save(out, format="JPEG", quality=85, optimize=True)
            return out.getvalue()
    except InvalidImage:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        raise InvalidImage("محتوای فایل تصویر معتبر نیست.")
