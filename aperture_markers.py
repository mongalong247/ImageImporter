"""
Aperture-slate marker table for the physical aperture fan-deck system.

Unlike lens presets (aruco_codes.py / resources/aruco_registry.json), this
is a fixed physical scale, not user-generated data -- so it lives here as a
hardcoded Python constant, not a JSON registry, and is kept physically
separate from aruco_registry.json so no reset/import/export flow for lens
presets can ever touch it.

ID range 101-124 is reserved for aperture markers. Lens presets use 1-99
(see aruco_codes.py); 100 and 125-150 are an intentional gap so the two
ranges can never collide, even via off-by-one bugs. This table is meant to
ship byte-identical across every build and every version -- a printed
blade from any deck, of any age, reads identically on any install.

ID 124 is permanently RESERVED and must never be assigned an f-stop or
written to. It exists so a marker ID always resolves to something
well-defined even if a future revision wants a dedicated "clear aperture"
no-op card -- until then, detecting it is just logged and ignored.
"""

APERTURE_ID_MIN = 101
APERTURE_ID_MAX = 124
APERTURE_RESERVED_ID = 124  # reserved -- do not assign, do not populate below

# f_stop is stored as a string matching the EXIF FNumber convention used
# elsewhere in the app (see lens_presets.json / aruco_codes.PRESET_FIELDS),
# e.g. "2.8" rather than a float, so it can be dropped straight into a
# metadata dict without reformatting.
APERTURE_MARKERS = {
    101: {"f_stop": "0.95", "tier": "full"},
    102: {"f_stop": "1.2",  "tier": "full"},
    103: {"f_stop": "1.4",  "tier": "full"},
    104: {"f_stop": "2",    "tier": "full"},
    105: {"f_stop": "2.8",  "tier": "full"},
    106: {"f_stop": "4",    "tier": "full"},
    107: {"f_stop": "5.6",  "tier": "full"},
    108: {"f_stop": "8",    "tier": "full"},
    109: {"f_stop": "11",   "tier": "full"},
    110: {"f_stop": "16",   "tier": "full"},
    111: {"f_stop": "22",   "tier": "full"},
    112: {"f_stop": "32",   "tier": "full"},
    113: {"f_stop": "1.1",  "tier": "half"},
    114: {"f_stop": "1.3",  "tier": "half"},
    115: {"f_stop": "1.7",  "tier": "half"},
    116: {"f_stop": "2.4",  "tier": "half"},
    117: {"f_stop": "3.3",  "tier": "half"},
    118: {"f_stop": "4.8",  "tier": "half"},
    119: {"f_stop": "6.7",  "tier": "half"},
    120: {"f_stop": "9.5",  "tier": "half"},
    121: {"f_stop": "13",   "tier": "half"},
    122: {"f_stop": "19",   "tier": "half"},
    123: {"f_stop": "27",   "tier": "half"},
    # 124 intentionally absent -- see APERTURE_RESERVED_ID.
}


def is_aperture_id(marker_id: int) -> bool:
    """True if marker_id falls in the aperture range (101-124), regardless
    of whether it's a populated f-stop or the reserved ID."""
    return APERTURE_ID_MIN <= marker_id <= APERTURE_ID_MAX


def get_aperture_fnumber(marker_id: int):
    """
    Returns the FNumber string for a detected aperture marker ID (e.g.
    "2.8"), or None if the ID is the reserved marker (124) or otherwise
    isn't populated in the table. Callers should treat None as "detected,
    but no action to take" and log it distinctly from an out-of-range ID.
    """
    entry = APERTURE_MARKERS.get(marker_id)
    return entry["f_stop"] if entry else None
