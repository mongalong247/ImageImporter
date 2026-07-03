"""
Turns a photo file (JPEG or RAW) into an image OpenCV can scan for a QR
code. This is step 3 of the QR lens-slate roadmap -- getting a decodable
frame -- kept separate from step 4 (actually running the QR detector on
it), which is built next.

Why RAW needs special handling: OpenCV's built-in codecs don't understand
RAW formats (.CR2, .NEF, .ARW, etc.), and a full RAW decode is a heavy,
slow dependency we don't want to add just to read a QR code out of one
slate frame. Nearly every RAW file already carries an embedded JPEG
preview -- the same image a camera's own LCD uses for playback -- and
ExifTool (already a dependency of this app) can pull that out directly.
We scan that instead of the RAW pixel data itself.
"""

import os

import cv2
import numpy as np

import exiftool_manager

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
