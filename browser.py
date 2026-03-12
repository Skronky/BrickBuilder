# BrickBuilder/browser.py
# Sidebar panel, search, and thumbnail grid for the parts browser.
# All logic that doesn't need bpy lives in plain functions at the top
# so it can be tested without Blender.
#
# Threading model:
# - Search runs once when the Search button is pressed, results cached in _results_cache
# - Thumbnails are fetched in daemon threads, one per part
# - Each thread calls tag_redraw() when its image lands so the grid updates live
# - _enum_items_cb only reads from cache — never hits the network

import os
import threading
import bpy
import bpy.utils.previews

from .thumbnails import search_parts_merged, fetch_thumbnail
from .constants  import MINIFIG_CATEGORY_IDS

# One preview collection for the entire addon lifetime.
_pcoll = None

# Search results cache — populated by the Search operator, read by the enum callback.
# Keyed by (query, minifig_only) so switching the checkbox doesn't re-fetch.
_results_cache = {}   # (query, minifig_only) -> list of part dicts
_active_query  = ("", True)

# Part thumbnails that arrived from threads but haven't been loaded into pcoll yet.
_pending_loads = {}   # part_num -> local filepath

# Persistent list for enum items — must be module-level, mutated in place.
# Blender holds a reference to strings in the list; if they get GC'd Blender
# crashes. Never reassign this variable — only .clear() + .extend() it.
_enum_items = []

# Color enum items — same GC-safe pattern as _enum_items
_color_enum_items = []


# ---------------------------------------------------------------------------
# Pure logic - testable without bpy
# ---------------------------------------------------------------------------

def build_enum_items(results, pcoll):
    """Convert Rebrickable search results into template_icon_view enum items.

    Returns immediately using whatever icons are already loaded.
    Thumbnails that haven't arrived yet get icon_id 0 (blank).
    """
    items = []
    for i, part in enumerate(results):
        part_num = part["part_num"]
        name     = part.get("name", part_num)
        icon_id  = pcoll[part_num].icon_id if part_num in pcoll else 0
        items.append((part_num, name, name, icon_id, i))

    return items if items else [("NONE", "No results", "", 0, 0)]


def filter_minifig(results):
    """Filter results to minifig-related categories only."""
    if not MINIFIG_CATEGORY_IDS:
        return results
    return [r for r in results if r.get("part_cat_id") in MINIFIG_CATEGORY_IDS]


def build_color_enum_items(colors, search=""):
    """Build enum items for the color picker, optionally filtered by search string.

    Each item: (ldraw_id, name, name, i)
    Falls back to a single placeholder if no colors loaded yet.
    """
    search = search.strip().lower()
    filtered = [c for c in colors if search in c["name"].lower()] if search else colors
    if not filtered:
        return [("14", "Yellow (default)", "Yellow (default)", 0)]
    return [(c["ldraw_id"], c["name"], f"#{c['rgb']}  LDraw:{c['ldraw_id']}", i)
            for i, c in enumerate(filtered)]


def _rebuild_color_enum(context):
    """Rebuild _color_enum_items from current search filter. Call from main thread only."""
    from .thumbnails import get_colors
    from . import get_api_key
    wm     = context.window_manager
    search = getattr(wm, "bb_color_search", "")
    colors = get_colors(get_api_key())
    _color_enum_items.clear()
    _color_enum_items.extend(build_color_enum_items(colors, search))


# ---------------------------------------------------------------------------
# Background thumbnail fetching
# ---------------------------------------------------------------------------

def _fetch_thumb_async(part_num, img_url, area):
    """Fetch one thumbnail in a background thread and tag_redraw when done."""
    local = fetch_thumbnail(img_url, part_num)
    if local and os.path.isfile(local):
        _pending_loads[part_num] = local
    if area:
        try:
            area.tag_redraw()
        except Exception:
            pass


def _flush_pending(pcoll):
    """Load any pending thumbnails into pcoll. Called from the main thread."""
    for part_num, path in list(_pending_loads.items()):
        if part_num not in pcoll and os.path.isfile(path):
            pcoll.load(part_num, path, 'IMAGE')
        del _pending_loads[part_num]


def _start_thumb_fetches(results, area):
    """Kick off background threads for all parts missing thumbnails."""
    from .thumbnails import thumb_path
    for part in results:
        part_num = part["part_num"]
        img_url  = part.get("part_img_url", "")
        if not img_url:
            continue
        if part_num in _pcoll:
            continue
        # Already on disk — no thread needed, just queue it
        if os.path.isfile(thumb_path(part_num)):
            _pending_loads[part_num] = thumb_path(part_num)
            continue
        threading.Thread(
            target = _fetch_thumb_async,
            args   = (part_num, img_url, area),
            daemon = True,
        ).start()


# ---------------------------------------------------------------------------
# Enum callback - called by Blender on every redraw, must be fast
# ---------------------------------------------------------------------------

# _enum_items is used directly via lambda in EnumProperty registration


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class BRICKBUILDER_OT_Search(bpy.types.Operator):
    """Search Rebrickable and populate the thumbnail grid"""
    bl_idname = "brickbuilder.search"
    bl_label  = "Search"

    def execute(self, context):
        global _active_query
        wm        = context.window_manager
        query     = wm.bb_search.strip()
        minifig   = wm.bb_minifig_only
        cache_key = (query, minifig)

        if not query:
            return {'CANCELLED'}

        if cache_key not in _results_cache:
            from . import get_api_key
            raw     = search_parts_merged(query, get_api_key())
            results = filter_minifig(raw) if minifig else raw
            _results_cache[cache_key] = results

        _active_query = cache_key

        area = next((a for a in context.screen.areas if a.type == 'VIEW_3D'), None)
        _start_thumb_fetches(_results_cache[cache_key], area)

        # Flush any on-disk thumbs into pcoll, then populate enum items
        _flush_pending(_pcoll)
        _enum_items.clear()
        _enum_items.extend(build_enum_items(_results_cache[cache_key], _pcoll))

        if area:
            area.tag_redraw()

        return {'FINISHED'}


class BRICKBUILDER_OT_FetchColors(bpy.types.Operator):
    """Fetch LEGO colors from Rebrickable and populate the color picker"""
    bl_idname = "brickbuilder.fetch_colors"
    bl_label  = "Load Colors"

    def execute(self, context):
        from .thumbnails import get_colors
        from . import get_api_key
        colors = get_colors(get_api_key())
        if not colors:
            self.report({'WARNING'}, "Could not fetch colors from Rebrickable")
            return {'CANCELLED'}
        _rebuild_color_enum(context)
        self.report({'INFO'}, f"Loaded {len(colors)} LEGO colors")
        return {'FINISHED'}


class BRICKBUILDER_OT_PlacePart(bpy.types.Operator):
    """Place the selected part into the scene at the 3D cursor"""
    bl_idname = "brickbuilder.place_part"
    bl_label  = "Place Part"

    def execute(self, context):
        wm       = context.window_manager
        part_num = wm.bb_selected_part
        if not part_num or part_num == "NONE":
            self.report({'WARNING'}, "No part selected")
            return {'CANCELLED'}

        # Get selected LDraw color code — fall back to 14 (Yellow) if picker not loaded
        color_code = "14"
        if _color_enum_items:
            selected = getattr(wm, "bb_color", None)
            if selected:
                color_code = selected

        bpy.ops.brickbuilder.import_part(part_num=part_num, color_code=color_code)
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

class BRICKBUILDER_PT_Browser(bpy.types.Panel):
    bl_label       = "BrickBuilder"
    bl_idname      = "BRICKBUILDER_PT_BROWSER"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = 'Brick Suite'
    bl_order       = 10

    def draw(self, context):
        layout = self.layout
        wm     = context.window_manager

        # Flush thumbnails that arrived from background threads
        if _pcoll and _pending_loads:
            _flush_pending(_pcoll)
            _enum_items.clear()
            _enum_items.extend(build_enum_items(_results_cache.get(_active_query, []), _pcoll))

        row = layout.row(align=True)
        row.prop(wm, "bb_search", text="", icon='VIEWZOOM')
        row.operator("brickbuilder.search", text="", icon='FILE_REFRESH')

        layout.prop(wm, "bb_minifig_only", text="Minifig parts only")
        layout.separator()

        if wm.bb_search.strip():
            results = _results_cache.get(_active_query, [])
            if results:
                layout.template_icon_view(
                    wm, "bb_selected_part",
                    show_labels=True,
                    scale=5.0,
                    scale_popup=6.0,
                )

                # Show source badge if selected part is LDraw-only
                selected = wm.bb_selected_part
                if selected and selected != "NONE":
                    part_data = next(
                        (p for p in results if p["part_num"] == selected), None
                    )
                    if part_data and part_data.get("source") == "ldraw":
                        row = layout.row()
                        row.alert = False
                        row.label(text="LDraw assembly", icon='LINKED')

                layout.separator()

                # Color picker
                box = layout.box()
                box.label(text="Color", icon='COLOR')
                if not _color_enum_items:
                    box.operator("brickbuilder.fetch_colors", icon='IMPORT')
                else:
                    row = box.row(align=True)
                    row.prop(wm, "bb_color_search", text="", icon='VIEWZOOM')
                    row.operator("brickbuilder.fetch_colors", text="", icon='FILE_REFRESH')
                    box.prop(wm, "bb_color", text="")

                layout.separator()
                layout.operator("brickbuilder.place_part", icon='IMPORT')
            else:
                layout.label(text="No results — press refresh", icon='INFO')
        else:
            layout.label(text="Search for a part above", icon='INFO')

        # LDraw index status hint
        from .ldraw_index import is_loaded
        if not is_loaded():
            layout.separator()
            layout.label(text="Add parts.lst for LDraw results", icon='ERROR')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def _on_color_search_update(self, context):
    """Called when bb_color_search changes — rebuild the filtered color enum."""
    _rebuild_color_enum(context)


def _register_props():
    wm = bpy.types.WindowManager
    wm.bb_search = bpy.props.StringProperty(
        name        = "Search",
        description = "Search Rebrickable parts library",
        default     = "",
    )
    _enum_items.clear()
    _enum_items.extend([("NONE", "No results", "", 0, 0)])
    wm.bb_selected_part = bpy.props.EnumProperty(
        name  = "Part",
        items = lambda self, context: _enum_items,
    )
    wm.bb_minifig_only = bpy.props.BoolProperty(
        name    = "Minifig parts only",
        default = True,
    )
    wm.bb_color_search = bpy.props.StringProperty(
        name        = "Color Search",
        description = "Filter colors by name",
        default     = "",
        update      = _on_color_search_update,
    )
    _color_enum_items.clear()
    _color_enum_items.extend([("14", "Yellow (default)", "Yellow — load colors to see all", 0)])
    wm.bb_color = bpy.props.EnumProperty(
        name        = "Color",
        description = "LDraw color for the placed part",
        items       = lambda self, context: _color_enum_items,
    )


def _unregister_props():
    wm = bpy.types.WindowManager
    for prop in ("bb_search", "bb_selected_part", "bb_minifig_only", "bb_color_search", "bb_color"):
        if hasattr(wm, prop):
            delattr(wm, prop)


classes = [
    BRICKBUILDER_OT_Search,
    BRICKBUILDER_OT_FetchColors,
    BRICKBUILDER_OT_PlacePart,
    BRICKBUILDER_PT_Browser,
]


def register():
    global _pcoll
    _pcoll = bpy.utils.previews.new()
    _pcoll.enum_items  = []   # persistent ref — strings must outlive the callback
    _pcoll.active_query = None
    for cls in classes:
        bpy.utils.register_class(cls)
    _register_props()


def unregister():
    global _pcoll
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    _unregister_props()
    if _pcoll:
        bpy.utils.previews.remove(_pcoll)
        _pcoll = None
