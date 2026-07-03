"""
QR code generation for lens presets.

This is step 1 of the QR lens-slate roadmap: turn a saved preset into a
printable QR code that can go inside a lens cap or a notebook. Reading
QR codes back out of photos at import time (via OpenCV) is a later step
and lives in a separate module once it's built, so this file stays small
and focused.

Each generated code encodes a compact, self-describing JSON payload
prefixed with a fixed marker string. The marker lets the future import-time
scanner tell a genuine lens-preset QR code apart from any other QR code
that might happen to appear in a frame (a shipping label, a poster, etc.)
before it even tries to parse the JSON.
"""

import io
import json

import qrcode
from PIL import Image, ImageDraw, ImageFont

# Bump this if the payload shape ever changes, so a future decoder can
# tell old and new codes apart and handle both.
QR_MARKER = "IMGIMPORTER-LENS-PRESET-V1:"

# Fields pulled from a preset dict, in the order they're written into the
# QR payload. Kept in sync with MetadataManagerPanel.get_active_metadata().
PRESET_FIELDS = (
    "LensMake", "LensModel", "FocalLength",
    "FNumber", "LensSerialNumber", "ImageDescription",
)


def _build_payload(preset_name: str, preset_data: dict) -> str:
    """Builds the compact marker-prefixed JSON string encoded into the QR code."""
    payload = {"name": preset_name}
    for field in PRESET_FIELDS:
        payload[field] = preset_data.get(field, "")
    # Compact separators keep the payload (and therefore the QR code) small,
    # which matters for print size and scan reliability.
    return QR_MARKER + json.dumps(payload, separators=(",", ":"))


def generate_preset_qr(preset_name: str, preset_data: dict, include_label: bool = True) -> Image.Image:
    """
    Builds a printable QR code image for a lens preset.

    Uses ExifTool-style generous error correction (~30% of the code can be
    damaged, obscured, or blurred and still decode) since this is meant to
    be printed small -- a lens cap insert -- and photographed handheld,
    both of which introduce noise that a scanned document wouldn't have.

    If include_label is True, the preset name is printed as a caption
    underneath, so a physical cap insert stays human-readable even without
    scanning it.

    Returns a PIL.Image.Image (RGB).
    """
    payload = _build_payload(preset_name, preset_data)

    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    if not include_label:
        return qr_image

    label_height = 40
    canvas = Image.new("RGB", (qr_image.width, qr_image.height + label_height), "white")
    canvas.paste(qr_image, (0, 0))

    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        # Falls back gracefully on systems without arial.ttf (e.g. Linux).
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), preset_name, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(
        ((canvas.width - text_width) / 2, qr_image.height + 8),
        preset_name, fill="black", font=font,
    )
    return canvas


def qr_image_to_png_bytes(image: Image.Image) -> bytes:
    """Converts a PIL Image to PNG bytes, e.g. for loading into a QPixmap."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
