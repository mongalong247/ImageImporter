"""
ArUco tag detection for lens presets: turns a photo file into a scannable
frame (same JPEG-direct / RAW-preview-via-ExifTool approach as the frozen
qr_scan.py) and decodes an ArUco marker ID from it.

Frame extraction is duplicated here rather than imported from qr_scan.py
so this module has zero dependency on the QR path, which is being kept
in the repo unused as a regression reference -- if QR ever needs to come
back, nothing in the active code path should need to change to make room
for it.
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

ARUCO_DICTIONARY = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_250)
_DETECTOR_PARAMS = cv2.aruco.DetectorParameters()
_detector = cv2.aruco.ArucoDetector(ARUCO_DICTIONARY, _DETECTOR_PARAMS)


def get_scannable_frame_with_info(file_path: str):
    """
    Returns a decoded image as a BGR numpy array (OpenCV's native format)
    plus a short human-readable description of how it was obtained --
    direct decode vs. which ExifTool tag supplied a RAW preview, plus its
    pixel dimensions -- useful for diagnosing a marker that isn't being
    detected because the source image turned out to be too small or the
    wrong tag was used.

    Returns (image_or_None, info_string).
    """
    if not file_path or not os.path.exists(file_path):
        return None, "file not found"

    ext = os.path.splitext(file_path)[1].lower()

    if ext in DIRECT_DECODE_EXTENSIONS:
        image = cv2.imread(file_path, cv2.IMREAD_COLOR)
        if image is None:
            return None, "direct decode failed"
        h, w = image.shape[:2]
        return image, f"direct decode, {w}x{h}"

    preview_bytes, source_tag = exiftool_manager.extract_preview_image_bytes(file_path)
    if not preview_bytes:
        return None, "no embedded preview or thumbnail found"

    buffer = np.frombuffer(preview_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        return None, f"embedded {source_tag} found but could not be decoded as an image"
    h, w = image.shape[:2]
    return image, f"RAW preview via {source_tag}, {w}x{h}"


def get_scannable_frame(file_path: str):
    """Same as get_scannable_frame_with_info(), without the diagnostic info string."""
    image, _info = get_scannable_frame_with_info(file_path)
    return image


def decode_aruco_id(image):
    """
    Runs OpenCV's ArUco detector against an already-loaded image (as
    returned by get_scannable_frame) and returns the first detected
    marker's integer ID, or None if no marker was found. Never raises.
    """
    if image is None:
        return None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    try:
        _corners, ids, _rejected = _detector.detectMarkers(gray)
    except Exception as e:
        print(f"[ArUco Error] OpenCV marker detection failed: {e}")
        return None

    if ids is None or len(ids) == 0:
        return None
    # ids is normally shaped (N, 1), but some OpenCV builds/detection
    # paths return (N,) instead -- flatten first so indexing is safe
    # regardless of which shape comes back.
    return int(np.asarray(ids).reshape(-1)[0])


def scan_file_for_aruco_id(file_path: str):
    """
    Convenience wrapper: extracts a scannable frame from file_path and
    decodes an ArUco marker ID from it, if present.

    Returns the integer ID, or None if the file has no scannable frame or
    no marker was found in it.
    """
    return decode_aruco_id(get_scannable_frame(file_path))