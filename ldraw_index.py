# BrickBuilder/ldraw_index.py
# Searches the bundled LDraw parts index (parts.lst).
#
# parts.lst format (one part per line):
#   3001.dat                 Brick  2 x  4
#   979.dat                  ~Minifig Standing (Complete)
#
# Lines starting with ~ are shortcuts/assemblies (pre-assembled models).
# The bundled file lives next to this module as "parts.lst".
# If it isn't present, LDraw search silently returns nothing.

import os
import re

_INDEX = None          # list of (part_num, description) tuples, loaded once
_INDEX_LOADED = False  # True even if the file was missing (avoids re-trying)

_LST_PATH = os.path.join(os.path.dirname(__file__), "parts.lst")

# Rebrickable thumbnail URL pattern — works for most parts
_RB_THUMB_URL = "https://cdn.rebrickable.com/media/parts/photos/0/{part_num}.jpg"


def _load_index():
    """Parse parts.lst into _INDEX. Can be called again after a fresh download."""
    global _INDEX, _INDEX_LOADED
    _INDEX_LOADED = True
    _INDEX = []  # reset before reload
    if not os.path.isfile(_LST_PATH):
        print("BrickBuilder: parts.lst not found — LDraw search disabled")
        _INDEX = []
        return

    entries = []
    with open(_LST_PATH, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            # Split on 2+ spaces — filename is left, description is right
            m = re.split(r"\s{2,}", line, maxsplit=1)
            if len(m) < 2:
                continue
            filename, desc = m[0].strip(), m[1].strip()
            # Strip the .dat extension to get the part number
            part_num = filename.lower()
            if part_num.endswith(".dat"):
                part_num = part_num[:-4]
            entries.append((part_num, desc))

    _INDEX = entries
    print(f"BrickBuilder: loaded LDraw index — {len(_INDEX)} parts")


def search_ldraw(query, max_results=24):
    """Search the LDraw parts index for query.

    Returns list of dicts compatible with Rebrickable search results:
      {part_num, name, part_img_url, part_cat_id, source}

    source="ldraw" so callers can distinguish these from Rebrickable results.
    Thumbnails use the Rebrickable CDN URL (best-effort — may 404 for some parts).
    """
    global _INDEX, _INDEX_LOADED
    if not _INDEX_LOADED:
        _load_index()
    if not _INDEX:
        return []

    q = query.strip().lower()
    if not q:
        return []

    results = []
    for part_num, desc in _INDEX:
        if q in part_num.lower() or q in desc.lower():
            results.append({
                "part_num":     part_num,
                "name":         desc,
                # Try Rebrickable CDN first — fetch_thumbnail handles 404 gracefully
                "part_img_url": _RB_THUMB_URL.format(part_num=part_num),
                "part_cat_id":  0,
                "source":       "ldraw",
            })
            if len(results) >= max_results:
                break

    return results


def is_loaded():
    """Return True if parts.lst was found and loaded."""
    global _INDEX_LOADED, _INDEX
    if not _INDEX_LOADED:
        _load_index()
    return bool(_INDEX)


# ---------------------------------------------------------------------------
# TODO: faster parts list generation
# ---------------------------------------------------------------------------
# Currently the only way to get parts.lst is running LDraw's mklist.exe
# which is slow. A faster alternative would be:
#
# 1. Scrape the LDraw Parts Tracker directly:
#    https://www.ldraw.org/library/official/parts.lst
#    This URL serves the pre-built file directly — no exe needed.
#    Just download it with urllib and save it next to this module.
#
# 2. Or build it ourselves from the LDraw CDN:
#    The gkjohnson mirror has all .dat files at:
#    https://raw.githubusercontent.com/gkjohnson/ldraw-parts-library/master/complete/ldraw/parts/
#    We could fetch the GitHub directory listing via the GitHub API
#    (no auth needed for public repos, returns JSON instantly) and
#    read just the first line of each .dat for the description.
#    GitHub API: https://api.github.com/repos/gkjohnson/ldraw-parts-library/contents/complete/ldraw/parts
#    This would give us a full index in one API call instead of 440.
#
# Option 1 is the fastest — it's literally one HTTP request.
# Option 2 is a good fallback if ldraw.org is down.
