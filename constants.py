# BrickBuilder/constants.py
# All magic numbers and config live here.
# API key is read from Blender preferences - see __init__.py for the prefs class.
# Do not hardcode the API key here.

import os

# LDraw scale - 1 LDU = 0.4mm
BRICK_SUITE_SCALE_LDRAW = 0.0004

# CDN for .dat files - gkjohnson's full LDraw library mirror
CDN_BASE = "https://raw.githubusercontent.com/gkjohnson/ldraw-parts-library/master/complete/ldraw"

# Rebrickable API
REBRICKABLE_API_BASE = "https://rebrickable.com/api/v3/lego"

# Read API key from environment variable as fallback during development.
# In production this comes from Blender addon preferences.
REBRICKABLE_API_KEY = os.environ.get("REBRICKABLE_API_KEY", "")

# Rebrickable category IDs for minifig parts.
# Verified against rebrickable.com/api/v3/lego/part_categories/
MINIFIG_CATEGORY_IDS = {
    13,   # Minifigs
    27,   # Minifig Accessories
    59,   # Minifig Heads
    60,   # Minifig Upper Body
    61,   # Minifig Lower Body
    65,   # Minifig Headwear
    70,   # Minifig Hipwear
    71,   # Minifig Neckwear
    72,   # Minifig Headwear Accessories
    73,   # Minifig Shields, Weapons, & Tools
}

# Local cache directories - both cleared by clear_cache() in preferences
CACHE_DIR_DAT   = os.path.join(os.path.expanduser("~"), ".brickbuilder", "ldraw_cache")
CACHE_DIR_THUMB = os.path.join(os.path.expanduser("~"), ".brickbuilder", "thumbnails")
