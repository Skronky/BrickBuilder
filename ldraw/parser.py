# BrickBuilder/ldraw/parser.py
# Reads part metadata from .dat file headers without loading geometry.
# Used to populate the browser with categories, keywords, and descriptions.
# Full geometry import is handled by cuddlyogre's pipeline - not here.

import os
from .network_filesystem import NetworkFileSystem

# Lines past this in a .dat header are geometry, not metadata.
# Parsing stops here to keep things fast.
_MAX_HEADER_LINES = 20


def get_part_info(part_id):
    """Fetch and parse the header of a .dat file for a given part ID.

    Returns a dict with keys: id, filename, description, category, keywords.
    Returns None if the file cannot be located.
    """
    filename = _to_filename(part_id)
    filepath = NetworkFileSystem.locate(filename)
    if filepath is None:
        return None
    return _parse_header(filepath, part_id)


def get_parts_in_category(category):
    """Return a list of part info dicts for all cached parts in a category.

    Only searches the local cache — does not fetch from CDN.
    Used to populate the browser after the user has placed a few parts.
    """
    results = []
    if not os.path.isdir(_cache_dir()):
        return results
    for fname in os.listdir(os.path.join(_cache_dir(), "parts")):
        if not fname.endswith(".dat"):
            continue
        info = _parse_header(os.path.join(_cache_dir(), "parts", fname), fname[:-4])
        if info and category.lower() in [c.lower() for c in info["category"]]:
            results.append(info)
    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_filename(part_id):
    # LDraw filenames are lowercase with .dat extension
    return part_id.lower().strip() + ".dat"


def _cache_dir():
    from .network_filesystem import _CACHE_DIR
    return _CACHE_DIR


def _parse_header(filepath, part_id):
    description = None
    category    = []
    keywords    = []

    try:
        with open(filepath, encoding="utf-8-sig", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= _MAX_HEADER_LINES:
                    break

                line = line.strip()
                if not line or not line.startswith("0 "):
                    continue

                # First meta line is always the description
                if description is None and not any(
                    line.startswith(p) for p in (
                        "0 Name:", "0 Author:", "0 !LDRAW_ORG",
                        "0 !LICENSE", "0 BFC", "0 !CATEGORY",
                        "0 !KEYWORDS", "0 !HISTORY", "0 //"
                    )
                ):
                    parts = line.split(maxsplit=1)
                    if len(parts) > 1:
                        description = parts[1]

                elif line.startswith("0 !CATEGORY "):
                    category.append(line.split(maxsplit=2)[2])

                elif line.startswith("0 !KEYWORDS "):
                    keywords += [k.strip() for k in line.split(maxsplit=2)[2].split(",")]

    except OSError:
        return None

    return {
        "id":          part_id,
        "filename":    _to_filename(part_id),
        "description": description or part_id,
        "category":    category,
        "keywords":    keywords,
    }
