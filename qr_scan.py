"""
Turns a photo file (JPEG or RAW) into an image OpenCV can scan for a QR
code, and decodes any lens-preset QR code found in it. This covers steps
3 and 4 of the QR lens-slate roadmap -- extraction and decoding -- kept
in one module since decoding is meaningless without a frame to decode.

Why RAW needs special handling: OpenCV's built-in codecs don't understand
RAW formats (.CR2, .NEF, .ARW, etc.), and a full RAW decode is a heavy,
slow dependency we don't want to add just to read a QR code out of one
slate frame. Nearly every RAW file already carries an embedded JPEG
preview -- the same image a camera's own LCD uses for playback -- and
ExifTool (already a dependency of this app) can pull that out directly.
We scan that instead of the RAW pixel data itself.
"""

import os
import json

import cv2
import numpy as np

import exiftool_manager
from qr_codes import QR_MARKER

# Formats OpenCV's built-in codecs can decode directly and reliably.
# Everything else this app recognizes as an image (RAW formats, HEIC/HEIF
# -- see app.IMAGE_EXTENSIONS) is routed through the ExifTool
# preview-extraction fallback below instead.
DIRECT_DECODE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.tif', '.tiff')


def get_scannable_frame(file_path: str):
    """
    Returns a decoded image as a BGR numpy array (OpenCV's native format),
    ready to hand to a QR detector, or None if no scannable image could be
    obtained.

    - .jpg/.jpeg/.png/.tif/.tiff are decoded directly.
    - Everything else (RAW formats, HEIC/HEIF) is routed through
      ExifTool's embedded preview/thumbnail extraction first, since
      OpenCV can't decode those directly.
    """
    if not file_path or not os.path.exists(file_path):
        return None

    ext = os.path.splitext(file_path)[1].lower()

    if ext in DIRECT_DECODE_EXTENSIONS:
        image = cv2.imread(file_path, cv2.IMREAD_COLOR)
        return image if image is not None else None

    preview_bytes = exiftool_manager.extract_preview_image_bytes(file_path)
    if not preview_bytes:
        return None

    buffer = np.frombuffer(preview_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    return image if image is not None else None


def decode_lens_preset_qr(image):
    """
    Runs OpenCV's QR detector against an already-loaded image (as returned
    by get_scannable_frame) and, if it finds a genuine lens-preset QR code
    -- recognized by its IMGIMPORTER-LENS-PRESET-V1: marker prefix, so a
    QR code that happens to appear in a frame for some unrelated reason
    (a poster, a shipping label) is safely ignored -- returns the decoded
    payload as a dict (the same shape generate_preset_qr encoded, e.g.
    {"name": ..., "LensMake": ..., "FocalLength": ..., ...}).

    Returns None if no QR code was found, it wasn't one of ours, or the
    payload couldn't be parsed. Never raises.
    """
    if image is None:
        return None

    detector = cv2.QRCodeDetector()
    try:
        data, _points, _straight_qrcode = detector.detectAndDecode(image)
    except Exception as e:
        print(f"[QR Error] OpenCV QR detection failed: {e}")
        return None

    if not data or not data.startswith(QR_MARKER):
        return None

    try:
        payload = json.loads(data[len(QR_MARKER):])
    except json.JSONDecodeError as e:
        print(f"[QR Error] Malformed lens-preset QR payload: {e}")
        return None

    if not isinstance(payload, dict) or "name" not in payload:
        return None

    return payload


def scan_file_for_lens_preset(file_path: str):
    """
    Convenience wrapper: extracts a scannable frame from file_path and
    decodes a lens-preset QR code from it, if present.

    Returns the decoded payload dict, or None if the file has no scannable
    frame or no lens-preset QR code was found in it.
    """
    return decode_lens_preset_qr(get_scannable_frame(file_path))
