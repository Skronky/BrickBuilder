# BrickBuilder — Developer Reference

Part of the BrickSuite ecosystem for LEGO animation in Blender.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Package Structure](#2-package-structure)
3. [Key Design Decisions](#3-key-design-decisions)
4. [Module Reference](#4-module-reference)
5. [Adding Support for New Parts](#5-adding-support-for-new-parts)
6. [Unit Tests](#6-unit-tests)
7. [Contributing](#7-contributing)
8. [Credits and Third-Party Code](#8-credits-and-third-party-code)
9. [Known Issues and Planned Work](#9-known-issues-and-planned-work)

---

## 1. Overview

BrickBuilder is a Blender 5.0 addon that lets animators search for LEGO parts, preview thumbnails, pick colors, and place fully-imported LDraw geometry at the 3D cursor. It is the parts browser and importer layer of the BrickSuite pipeline.

Search results are drawn from two sources simultaneously:

- **Rebrickable** — live API search with thumbnail images
- **Bundled LDraw index (`parts.lst`)** — 22,000+ parts including shortcuts and assemblies, works offline

Duplicate results are deduplicated automatically. Rebrickable results appear first since they carry thumbnail URLs. LDraw-only results (such as full minifig assemblies like `979.dat`) follow.

---

## 2. Package Structure

| File | Purpose |
|------|---------|
| `__init__.py` | Addon entry point. Preferences class (API key). Download Parts Index operator. register/unregister. |
| `browser.py` | Sidebar panel, search operator, thumbnail grid (EnumProperty + template_icon_view), color picker. |
| `thumbnails.py` | Rebrickable API calls. Merged search. Thumbnail download and local cache. Color fetch. |
| `placer.py` | LDraw import operator. Assembly detection (`is_assembly_file`). Stud snap math. |
| `ldraw_index.py` | Bundled `parts.lst` parser and searcher. Loaded once on first search. |
| `constants.py` | All magic numbers: API base URL, CDN URL, cache dirs, minifig category IDs, LDraw scale. |
| `bridge.py` | BrickSuite handoff operators (placeholder for inter-addon communication). |
| `parts.lst` | Bundled LDraw parts index. 22,695 entries. Replace to update. |
| `ldraw/` | Lightweight LDraw CDN filesystem. Fetches `.dat` files from gkjohnson's GitHub mirror. |
| `inc/` | Bundled ExportLDraw engine by cuddlyogre. Handles full LDraw parsing and Blender mesh creation. |

---

## 3. Key Design Decisions

### 3.1 EnumProperty GC Safety

Blender's `EnumProperty` holds raw C pointers to item strings. If Python garbage-collects the list, Blender crashes. BrickBuilder uses a module-level `_enum_items` list that is mutated in-place (`.clear()` + `.extend()`) rather than reassigned. The same pattern applies to `_color_enum_items`.

### 3.2 Threading Model

Thumbnail fetches run in daemon threads. They write to `_pending_loads` (a dict keyed by `part_num`). The main thread flushes `_pending_loads` into the preview collection on the next redraw via `_flush_pending()`. This keeps the UI responsive during network I/O.

The `parts.lst` downloader in preferences also runs in a daemon thread. It writes to a `.tmp` file and only renames it to `parts.lst` on success — so a failed download never corrupts the existing index.

### 3.3 Dual Search and Deduplication

`search_parts_merged()` in `thumbnails.py` calls both `search_parts()` (Rebrickable) and `search_ldraw()` (LDraw index) and merges results. Deduplication is handled by a `seen` set keyed on `part_num`. Rebrickable entries always win on conflict because they carry verified thumbnail URLs.

### 3.4 Assembly vs Single Part Import

`is_assembly_file()` in `placer.py` peeks at the first non-comment lines of a `.dat` file and checks for the `!LDRAW_ORG Shortcut` tag. If found, `_do_import_assembly()` is called with `parent_to_empty=True` so the cuddlyogre engine groups all sub-parts under one Empty. The Empty is moved to the 3D cursor so the whole figure translates as a unit. Stud snap is skipped for assemblies.

### 3.5 LDraw Scale

LDraw uses 1 LDU = 0.4mm. The constant `BRICK_SUITE_SCALE_LDRAW = 0.0004` is defined in `constants.py`. This differs from BrickSuite/EpicFigRig's Mecabricks scale (`0.032`). Scale normalisation for AutoRig compatibility is a planned feature for v2.

### 3.6 ImportOptions.json Stability

The bundled cuddlyogre engine saves settings to `ImportOptions.json`. A long-standing bug caused it to write `null` to the file when `cls.settings` was `None`. Three guards were added to `import_settings.py`:

- `save_settings()`: `if cls.settings is not None:` guard before writing
- `apply_settings()`: `if cls.settings is None: cls.load_settings()` before applying
- `load_settings()`: uses `type.__setattr__` to bypass the custom `__setattr__` override during initial load

---

## 4. Module Reference

### thumbnails.py

#### `search_parts_merged(query, api_key, page_size=24)`
Primary search function. Calls both Rebrickable and LDraw index, merges results, deduplicates by `part_num`. Returns list of dicts with keys: `part_num`, `name`, `part_img_url`, `part_cat_id`, `source`.

#### `search_parts(query, api_key, page_size=24)`
Rebrickable-only search. Results cached in `_META_CACHE` keyed by query string.

#### `get_part(part_num, api_key)`
Fetches a single part by ID. Falls back to `_search_by_external_id()` if the direct lookup 404s (handles Rebrickable vs LDraw ID mismatches). Returns dict with `ldraw_id` field.

#### `get_colors(api_key)`
Fetches all Rebrickable colors that have at least one LDraw external ID. Cached for the addon lifetime in `_COLORS_CACHE`.

---

### browser.py

#### `build_enum_items(results, pcoll)`
Converts a list of part dicts into Blender `EnumProperty` items. Returns the `NONE` sentinel when results is empty. Reads `icon_id` from `pcoll` — returns `0` (blank) if the thumbnail hasn't loaded yet.

#### `filter_minifig(results)`
Filters results to parts in `MINIFIG_CATEGORY_IDS`. Pass-through if the set is empty.

#### `build_color_enum_items(colors, search='')`
Builds color dropdown items from the fetched color list, optionally filtered by search string. Returns a Yellow fallback item when no colors match.

---

### placer.py

#### `is_assembly_file(filepath)`
Reads the `.dat` header and returns `True` if `!LDRAW_ORG Shortcut` is found. Returns `False` on any read error. Safe to call on missing files.

#### `find_nearest_stud(new_part_verts, existing_verts, threshold)`
Pure math. Returns the offset `Vector` to apply for stud snapping, or `None` if no vertex pair is within threshold distance.

---

### ldraw_index.py

#### `search_ldraw(query, max_results=24)`
Searches the in-memory LDraw index. Matches against both `part_num` and description. Loads `parts.lst` on first call. Returns `[]` on empty query or missing file.

#### `_load_index()`
Parses `parts.lst` into the `_INDEX` list. Can be called again after a fresh download — resets `_INDEX` to `[]` before reloading. The bundled file lives at the same directory level as this module.

---

## 5. Adding Support for New Parts

For parts that Rebrickable knows about: no action needed, they appear in search results automatically.

For LDraw-only parts not in the bundled `parts.lst`: update `parts.lst` with the new entry in the standard LDraw format:

```
partnumber.dat          Part Description Here
```

For minifig parts not recognised by EpicFigRig AutoRig: add the part ID to the appropriate list in `BrickSuite/constants.py` (`BRICK_HEAD`, `BRICK_ARM_LEFT`, etc.). The `BRICK_BONE_MAP` dict is rebuilt automatically.

---

## 6. Unit Tests

Run from the `BrickBuilder/` directory with:

```bash
python3 tests/run_tests.py
```

`bpy` is mocked via a lightweight stub. Tests cover:

- **constants**: API URL, LDraw scale, category IDs
- **thumbnails**: `thumb_path`, `search_parts_merged` deduplication, source ordering
- **browser**: `build_enum_items` (empty, pcoll hit, pcoll miss), `filter_minifig`, `build_color_enum_items` (filter, fallback)
- **ldraw_index**: `979` search, empty query, `is_loaded`, minifig head search
- **placer**: `find_nearest_stud` (hit, miss, empty input), `is_assembly_file` (shortcut, part, geometry-only, missing file)
- **import_settings**: None guards, `type.__setattr__` bypass

All 38 Python files pass AST syntax check. All 27 logic tests pass.

---

## 7. Contributing

Bug reports and pull requests are welcome. The most impactful contributions are:

- Updated `parts.lst` files with more complete LDraw coverage
- New part IDs for EpicFigRig AutoRig recognition (in `BrickSuite/constants.py`)
- Scale normalisation between LDraw and Mecabricks (`BRICK_SUITE_SCALE_LDRAW` vs `0.032`)
- Lighting/material fixes for LDraw-imported parts under HDRI sky textures

Before opening a PR please test your changes with the unit test suite and include a description of what part IDs or features you are adding.

---

## 8. Credits and Third-Party Code

### ExportLDraw — Matthew Morrison (cuddlyogre)
The LDraw import engine bundled in `inc/` is based on ExportLDraw by Matthew Morrison (cuddlyogre). The `inc/` folder contains a modified copy of this engine adapted for use as an embedded library.
- License: GPL v2+
- https://github.com/cuddlyogre/ExportLDraw

### ImportLDraw — Toby Lobster
cuddlyogre's ExportLDraw was itself inspired by and learned from ImportLDraw by Toby Lobster. Acknowledged here as the foundational work for LDraw import in Blender.
- License: GPL
- https://github.com/TobyLobster/ImportLDraw

### LDraw Parts CDN — gkjohnson
The `ldraw/network_filesystem.py` module fetches `.dat` files from gkjohnson's ldraw-parts-library GitHub mirror. This mirror provides the complete official and unofficial LDraw library accessible over HTTPS without requiring a local LDraw installation.
- https://github.com/gkjohnson/ldraw-parts-library

### Rebrickable
Part search, metadata, and thumbnail images are provided by the Rebrickable API. A free API key is required.
- https://rebrickable.com

### LDraw Community
The bundled `parts.lst` index and all `.dat` geometry files are created and maintained by the LDraw community. Parts data is licensed under CC BY 4.0.
- https://www.ldraw.org

### EpicFigRig Team
BrickBuilder is designed to feed into the EpicFigRig rigging system. EpicFigRig was created by **Reecey Bricks**, **JabLab**, **IX Productions**, **Citrine's Animations**, **Jambo**, **Owenator Productions**, and **Golden Ninja Ben**.
- License: GPL v3
- https://github.com/BlenderBricks/EpicFigRig

---

## 9. Known Issues and Planned Work

- **EpicFigRig integration: NOT YET IMPLEMENTED in v1.0.** LDraw imports at `BRICK_SUITE_SCALE_LDRAW` (`0.0004`) while EpicFigRig expects Mecabricks scale (`0.032`). Running AutoRig on a BrickBuilder-placed part will not work correctly yet. A NormalizeScale step and mesh data rename pass are required. Planned for a future update.
- **LDraw material lighting:** parts imported under HDRI sky textures show an incorrect white sheen. Root cause is likely in `blender_materials.py` node group values. Investigation pending.
- **Scale mismatch:** LDraw imports at `BRICK_SUITE_SCALE_LDRAW` (`0.0004`) while EpicFigRig expects Mecabricks scale (`0.032`). A NormalizeScale step is needed before AutoRig will work correctly on LDraw imports.
- **parts.lst coverage:** the bundled index has 22,695 entries. The full LDraw library has ~45,000. Contributions of more complete index files are welcome.
- **Minifig object naming:** LDraw sub-part mesh data is named after the `.dat` filename. AutoRig looks for Mecabricks-style IDs. A rename pass after import is needed to bridge the two systems.

---

*BrickBuilder v1.0 — BrickSuite Contributors — GPL v3.0*
