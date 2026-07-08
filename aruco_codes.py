"""
ArUco tag generation for lens presets -- the successor to the QR-code
approach in qr_codes.py (kept in the repo, unused, as an easy regression
path). ArUco markers are purpose-built for robust detection under
real-world shooting conditions (blur, skew, partial occlusion, distance,
poor print quality) in a way general-purpose QR codes aren't, at the cost
of only carrying a small integer ID rather than the full preset payload --
so this app now needs a local ID -> preset lookup (built in app.py from
the presets file), where the QR version didn't need one at all.

Known trade-off worth remembering: a printed tag is only meaningful to a
copy of the app whose local lens_presets.json has a matching ArucoId.
Unlike the QR version, these tags aren't self-contained -- sharing a
printed tag with someone else also means sharing (or reconciling) the
underlying preset data.
"""

import io
import os
import json

import cv2
from PIL import Image, ImageDraw, ImageFont

import paths

# DICT_4X4_250 costs nothing over a smaller dictionary (same marker
# blockiness, same detection robustness) but leaves headroom well past
# the ~30 presets in scope today.
ARUCO_DICTIONARY = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_250)

MARKER_PIXELS = 600      # generated marker resolution, before border/label are added
MARKER_BORDER_BITS = 1   # matches OpenCV's default quiet-zone expectation

# Fields pulled from a preset dict when building the ID -> preset lookup
# at import time. Kept in sync with MetadataManagerPanel.get_active_metadata().
PRESET_FIELDS = (
    "LensMake", "LensModel", "FocalLength",
    "FNumber", "LensSerialNumber", "ImageDescription",
)

REGISTRY_PATH = os.path.join(paths.RESOURCES_DIR, "aruco_registry.json")


def _load_registry() -> dict:
    if os.path.exists(REGISTRY_PATH):
        try:
            with open(REGISTRY_PATH, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"next_id": 1}


def _save_registry(registry: dict):
    os.makedirs(paths.RESOURCES_DIR, exist_ok=True)
    with open(REGISTRY_PATH, 'w') as f:
        json.dump(registry, f, indent=4)


def get_or_assign_id(preset_data: dict) -> int:
    """
    Returns the preset's existing ArucoId if it already has one, or
    assigns the next never-before-used ID and returns that.

    IDs are drawn from a monotonically increasing counter and are never
    reused, even after a preset carrying one is deleted -- otherwise a
    physically printed lens cap could silently start pointing at a
    completely different preset months later, with no way to tell just
    by looking at it.

    NOTE: this only returns the ID -- it doesn't persist it into the
    preset or save the presets file. The caller (MetadataManagerPanel)
    owns that, since it owns the presets dict and its save routine.
    """
    existing = preset_data.get("ArucoId")
    if existing:
        return existing

    registry = _load_registry()
    new_id = registry["next_id"]
    registry["next_id"] = new_id + 1
    _save_registry(registry)
    return new_id


def generate_aruco_tag(preset_name: str, aruco_id: int, include_label: bool = True) -> Image.Image:
    """
    Builds a printable ArUco marker image for a lens preset's assigned ID.

    Returns a PIL.Image.Image (RGB). If include_label is True, the ID and
    preset name are printed as a caption underneath, so a physical cap
    insert stays human-readable without needing to scan it.
    """
    marker_array = cv2.aruco.generateImageMarker(
        ARUCO_DICTIONARY, aruco_id, MARKER_PIXELS, borderBits=MARKER_BORDER_BITS
    )
    marker_image = Image.fromarray(marker_array).convert("RGB")

    if not include_label:
        return marker_image

    label_height = 50
    canvas = Image.new("RGB", (marker_image.width, marker_image.height + label_height), "white")
    canvas.paste(marker_image, (0, 0))

    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", 26)
    except Exception:
        # Falls back gracefully on systems without arial.ttf (e.g. Linux).
        font = ImageFont.load_default()

    label_text = f"#{aruco_id:03d}  {preset_name}"
    bbox = draw.textbbox((0, 0), label_text, font=font)
    text_width = bbox[2] - bbox[0]
    draw.text(
        ((canvas.width - text_width) / 2, marker_image.height + 10),
        label_text, fill="black", font=font,
    )
    return canvas


def marker_image_to_png_bytes(image: Image.Image) -> bytes:
    """Converts a PIL Image to PNG bytes, e.g. for loading into a QPixmap."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
