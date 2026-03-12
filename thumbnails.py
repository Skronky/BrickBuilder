# BrickBuilder/thumbnails.py
# Rebrickable API search and thumbnail fetching.

import os
import json
import urllib.request
import urllib.error
import urllib.parse

from .constants import REBRICKABLE_API_BASE, CACHE_DIR_THUMB

_META_CACHE   = {}   # in-memory: query -> list of part dicts
_COLORS_CACHE = []   # in-memory: fetched once, filtered to LDraw-mapped colors


def get_colors(api_key):
    """Fetch all Rebrickable colors that have an LDraw ID. Cached for addon lifetime.

    Returns list of dicts: {id, name, rgb, ldraw_id}
    Only colors with at least one LDraw external ID are included.
    """
    global _COLORS_CACHE
    if _COLORS_CACHE:
        return _COLORS_CACHE

    data = _api_get(f"{REBRICKABLE_API_BASE}/colors/?page_size=1000", api_key)
    if not data:
        return []

    colors = []
    for c in data.get("results", []):
        ldraw_ids = c.get("external_ids", {}).get("LDraw", {}).get("ext_ids", [])
        if not ldraw_ids:
            continue
        colors.append({
            "id":       str(c["id"]),
            "name":     c["name"],
            "rgb":      c.get("rgb", "FFFFFF"),
            "ldraw_id": str(ldraw_ids[0]),
        })

    colors.sort(key=lambda c: c["name"].lower())
    _COLORS_CACHE = colors
    return _COLORS_CACHE


def search_parts_merged(query, api_key, page_size=24):
    """Search both Rebrickable and the LDraw index, merge results.

    LDraw results are appended after Rebrickable ones.  Duplicates (same
    part_num from both sources) are deduplicated — Rebrickable entry wins
    because it has a guaranteed thumbnail URL.

    Returns list of dicts with an extra 'source' key: 'rebrickable' or 'ldraw'.
    """
    from .ldraw_index import search_ldraw

    rb_results    = search_parts(query, api_key, page_size=page_size)
    ldraw_results = search_ldraw(query, max_results=page_size)

    # Tag Rebrickable results
    for r in rb_results:
        r.setdefault("source", "rebrickable")

    # Deduplicate: skip LDraw entries whose part_num already appears in RB results
    seen = {r["part_num"] for r in rb_results}
    merged = list(rb_results)
    for r in ldraw_results:
        if r["part_num"] not in seen:
            merged.append(r)
            seen.add(r["part_num"])

    return merged


def search_parts(query, api_key, page_size=24):
    """Search Rebrickable for parts. Returns list of dicts or empty list."""
    if query in _META_CACHE:
        return _META_CACHE[query]

    params  = urllib.parse.urlencode({"search": query, "page_size": page_size})
    data    = _api_get(f"{REBRICKABLE_API_BASE}/parts/?{params}", api_key)
    if data is None:
        return []

    results = [
        {
            "part_num":     p.get("part_num", ""),
            "name":         p.get("name", ""),
            "part_img_url": p.get("part_img_url", ""),
            "part_cat_id":  p.get("part_cat_id", 0),
        }
        for p in data.get("results", [])
    ]
    _META_CACHE[query] = results
    return results


def get_part(part_num, api_key):
    """Fetch metadata for a single part. Returns dict or None.

    Falls back to a search when the direct lookup returns 404 (e.g. parts
    whose Rebrickable ID differs from their BrickLink/LDraw ID like 3626ap01
    -> 3626apr0001). The fallback confirms the match via external_ids so a
    fuzzy text hit on an unrelated part is never returned.
    """
    data = _api_get(f"{REBRICKABLE_API_BASE}/parts/{part_num}/", api_key)
    if data is None:
        data = _search_by_external_id(part_num, api_key)
    if data is None:
        return None
    ldraw_ids = data.get("external_ids", {}).get("LDraw", [])
    return {
        "part_num":     data.get("part_num", ""),
        "name":         data.get("name", ""),
        "part_img_url": data.get("part_img_url", ""),
        "part_cat_id":  data.get("part_cat_id", 0),
        "ldraw_id":     ldraw_ids[0] if ldraw_ids else data.get("part_num", ""),
    }


def _search_by_external_id(part_num, api_key):
    """Search for a part by external ID and verify the match. Returns raw API dict or None."""
    params = urllib.parse.urlencode({"search": part_num, "page_size": 5})
    data   = _api_get(f"{REBRICKABLE_API_BASE}/parts/?{params}", api_key)
    if not data:
        return None
    for result in data.get("results", []):
        all_ids = [eid for ids in result.get("external_ids", {}).values() for eid in ids]
        if part_num in all_ids:
            return result
    return None


def fetch_thumbnail(part_img_url, part_num):
    """Download thumbnail to local cache. Returns local path or None."""
    if not part_img_url:
        return None
    path = thumb_path(part_num)
    if os.path.isfile(path):
        return path
    try:
        os.makedirs(CACHE_DIR_THUMB, exist_ok=True)
        urllib.request.urlretrieve(part_img_url, path)
        return path
    except (urllib.error.URLError, OSError):
        return None


def thumb_path(part_num):
    return os.path.join(CACHE_DIR_THUMB, f"{part_num}.png")


def clear_cache():
    import shutil
    _META_CACHE.clear()
    _COLORS_CACHE.clear()
    if os.path.isdir(CACHE_DIR_THUMB):
        shutil.rmtree(CACHE_DIR_THUMB)


def _api_get(url, api_key):
    req = urllib.request.Request(url, headers={"Authorization": f"key {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"BrickBuilder: Rebrickable API error {e.code} for {url}")
        return None
    except (urllib.error.URLError, OSError) as e:
        print(f"BrickBuilder: network error: {e}")
        return None
