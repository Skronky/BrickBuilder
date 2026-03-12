# BrickBuilder/__init__.py

bl_info = {
    "name":        "BrickBuilder",
    "author":      "BrickSuite Contributors",
    "version":     (1, 0, 0),
    "blender":     (5, 0, 0),
    "location":    "View3D > Sidebar > Brick Suite",
    "description": "LDraw parts browser for Blender. Search, place, and rig LEGO parts.",
    "category":    "Import-Export",
}

import os
import threading
import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty

from .browser         import register  as _browser_register, unregister as _browser_unregister
from .placer          import classes   as _placer_classes
from .bridge          import classes   as _bridge_classes
from .inc.ldraw_props import register as _ldraw_props_register, unregister as _ldraw_props_unregister

# URL for the pybricks LDraw mirror — full official library including parts.lst
_PARTS_LST_URL  = "https://raw.githubusercontent.com/pybricks/ldraw/master/parts.lst"
_PARTS_LST_PATH = os.path.join(os.path.dirname(__file__), "parts.lst")

# Download state — read by the preferences draw() to show progress
_dl_status = {"state": "idle", "msg": ""}   # state: idle | running | done | error


def _download_parts_lst():
    """Download parts.lst in a background thread. Never touches bpy directly."""
    import urllib.request
    import urllib.error

    _dl_status["state"] = "running"
    _dl_status["msg"]   = "Downloading…"

    try:
        tmp = _PARTS_LST_PATH + ".tmp"
        urllib.request.urlretrieve(_PARTS_LST_URL, tmp)

        # Count lines so we can report how many parts were fetched
        with open(tmp, "r", encoding="utf-8", errors="replace") as f:
            count = sum(1 for ln in f if ln.strip() and not ln.startswith("#"))

        # Atomic replace — if anything above failed the old file is untouched
        if os.path.isfile(_PARTS_LST_PATH):
            os.remove(_PARTS_LST_PATH)
        os.rename(tmp, _PARTS_LST_PATH)

        # Reload the in-memory index so the next search picks it up immediately
        from .ldraw_index import _load_index
        _load_index()

        _dl_status["state"] = "done"
        _dl_status["msg"]   = f"Done — {count:,} parts loaded"

    except Exception as e:
        _dl_status["state"] = "error"
        _dl_status["msg"]   = f"Failed: {e}"
        # Clean up temp file if it exists
        try:
            if os.path.isfile(_PARTS_LST_PATH + ".tmp"):
                os.remove(_PARTS_LST_PATH + ".tmp")
        except OSError:
            pass


class BRICKBUILDER_OT_DownloadPartsLst(bpy.types.Operator):
    """Download the LDraw parts index in the background (won't freeze Blender)"""
    bl_idname = "brickbuilder.download_parts_lst"
    bl_label  = "Download Parts Index"

    def execute(self, context):
        if _dl_status["state"] == "running":
            self.report({'WARNING'}, "Download already in progress")
            return {'CANCELLED'}

        _dl_status["state"] = "running"
        _dl_status["msg"]   = "Starting…"

        t = threading.Thread(target=_download_parts_lst, daemon=True)
        t.start()

        self.report({'INFO'}, "Downloading parts.lst in background…")
        return {'FINISHED'}


class BrickBuilderPreferences(AddonPreferences):
    bl_idname = __name__

    api_key: StringProperty(
        name        = "Rebrickable API Key",
        description = "Get yours free at rebrickable.com/api",
        default     = "",
        subtype     = 'PASSWORD',
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="Get a free API key at rebrickable.com/api")
        layout.prop(self, "api_key")
        layout.separator()

        # Parts index section
        box = layout.box()
        box.label(text="LDraw Parts Index", icon='PRESET')

        has_index = os.path.isfile(_PARTS_LST_PATH)
        state     = _dl_status["state"]

        if state == "running":
            row = box.row()
            row.label(text=_dl_status["msg"], icon='TIME')

        elif state == "done":
            row = box.row()
            row.label(text=_dl_status["msg"], icon='CHECKMARK')
            box.operator("brickbuilder.download_parts_lst",
                         text="Re-download", icon='FILE_REFRESH')

        elif state == "error":
            row = box.row()
            row.alert = True
            row.label(text=_dl_status["msg"], icon='ERROR')
            box.operator("brickbuilder.download_parts_lst",
                         text="Retry Download", icon='FILE_REFRESH')

        else:  # idle
            if has_index:
                box.label(text="parts.lst found ✓", icon='CHECKMARK')
                box.operator("brickbuilder.download_parts_lst",
                             text="Re-download", icon='FILE_REFRESH')
            else:
                box.label(text="No parts index yet — LDraw search disabled",
                          icon='ERROR')
                box.operator("brickbuilder.download_parts_lst",
                             text="Download Parts Index (~1MB)", icon='IMPORT')


def get_api_key():
    """Read the API key from addon preferences. Returns empty string if not set."""
    prefs = bpy.context.preferences.addons.get(__name__)
    if prefs:
        return prefs.preferences.api_key
    return ""


def register():
    _ldraw_props_register()
    bpy.utils.register_class(BRICKBUILDER_OT_DownloadPartsLst)
    bpy.utils.register_class(BrickBuilderPreferences)
    for cls in [*_placer_classes, *_bridge_classes]:
        bpy.utils.register_class(cls)
    _browser_register()


def unregister():
    _browser_unregister()
    for cls in reversed([*_placer_classes, *_bridge_classes]):
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_class(BrickBuilderPreferences)
    bpy.utils.unregister_class(BRICKBUILDER_OT_DownloadPartsLst)
    _ldraw_props_unregister()
