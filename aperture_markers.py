"""
Aperture-slate marker table for the physical aperture fan-deck system.

Unlike lens presets (aruco_codes.py / resources/aruco_registry.json), this
is a fixed physical scale, not user-generated data -- so it lives here as a
hardcoded Python constant, not a JSON registry, and is kept physically
separate from aruco_registry.json so no reset/import/export flow for lens
presets can ever touch it.

ID range 101-130 is reserved for aperture markers. Lens presets use 1-99
(see aruco_codes.py); 100 and 131-150 are an intentional gap so the two
ranges can never collide, even via off-by-one bugs. This table is meant to
ship byte-identical across every build and every version -- a printed
blade from any deck, of any age, reads identically on any install.

Only 101-122 are populated at launch (22 values). 123-130 are held spare,
permanently RESERVED and never assigned an f-stop -- for real-world vintage
stops encountered later (e.g. f/2.2, f/25, T-stop-marked cine values).
Detecting a spare ID is logged and ignored, same as any other unpopulated
aperture ID; there's nothing special-cased about any one ID within 123-130.

Values are empirical, not purely geometric: half-stops reflect what
manufacturers actually printed on vintage/manual aperture rings (both
f/1.7 and f/1.8 appear as distinct, genuinely-seen values), not theoretical
geometric means between full stops. IDs are assigned in strict ascending
f-stop order (full and half stops interleaved) so future insertions stay
legible. ID order is NOT guaranteed to stay value-order past this initial
release -- new discoveries get slotted into 123-130 regardless of where
they'd numerically sit, so nobody should ever "clean up"/renumber this
table; every printed deck already in the wild depends on it staying put.

There are deliberately no half-stop entries between 0.95-1.2 or 1.2-1.4 --
those intervals are rare/fast enough that manufacturers essentially never
click a half-stop there, confirmed against real-world vintage glass.
"""

APERTURE_ID_MIN = 101
APERTURE_ID_MAX = 130

# f_stop is stored as a string matching the EXIF FNumber convention used
# elsewhere in the app (see lens_presets.json / aruco_codes.PRESET_FIELDS),
# e.g. "2.8" rather than a float, so it can be dropped straight into a
# metadata dict without reformatting.
APERTURE_MARKERS = {
    101: {"f_stop": "0.95", "tier": "full"},
    102: {"f_stop": "1.2",  "tier": "full"},
    103: {"f_stop": "1.4",  "tier": "full"},
    104: {"f_stop": "1.7",  "tier": "half"},
    105: {"f_stop": "1.8",  "tier": "half"},
    106: {"f_stop": "2",    "tier": "full"},
    107: {"f_stop": "2.5",  "tier": "half"},
    108: {"f_stop": "2.8",  "tier": "full"},
    109: {"f_stop": "3.5",  "tier": "half"},
    110: {"f_stop": "4",    "tier": "full"},
    111: {"f_stop": "4.5",  "tier": "half"},
    112: {"f_stop": "5.6",  "tier": "full"},
    113: {"f_stop": "6.3",  "tier": "half"},
    114: {"f_stop": "8",    "tier": "full"},
    115: {"f_stop": "9.5",  "tier": "half"},
    116: {"f_stop": "11",   "tier": "full"},
    117: {"f_stop": "13",   "tier": "half"},
    118: {"f_stop": "16",   "tier": "full"},
    119: {"f_stop": "19",   "tier": "half"},
    120: {"f_stop": "22",   "tier": "full"},
    121: {"f_stop": "27",   "tier": "half"},
    122: {"f_stop": "32",   "tier": "full"},
    # 123-130 intentionally absent -- spare/reserved, see module docstring.
}


def is_aperture_id(marker_id: int) -> bool:
    """True if marker_id falls in the aperture range (101-130), regardless
    of whether it's a populated f-stop or one of the spare/reserved IDs."""
    return APERTURE_ID_MIN <= marker_id <= APERTURE_ID_MAX


def get_aperture_fnumber(marker_id: int):
    """
    Returns the FNumber string for a detected aperture marker ID (e.g.
    "2.8"), or None if the ID is one of the spare/reserved IDs (123-130)
    or otherwise isn't populated in the table. Callers should treat None
    as "detected, but no action to take" and log it distinctly from an
    out-of-range ID.
    """
    entry = APERTURE_MARKERS.get(marker_id)
    return entry["f_stop"] if entry else None
