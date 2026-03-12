# BrickBuilder/placer.py
# Imports a .dat part into the scene and places it at the 3D cursor.
# Stud snapping aligns the part to the nearest stud on an existing part.
# All pure math lives in plain functions so it can be tested without bpy.
#
# Single parts (.dat with geometry) are imported directly.
# Assembly/shortcut files (like 979.dat — full minifig) contain multiple
# sub-parts with transformation matrices. These are imported with
# parent_to_empty=True so all sub-parts are grouped under one Empty object
# that can be moved/rotated as a unit.

import bpy
import mathutils

from .ldraw.network_filesystem import NetworkFileSystem
from .constants                 import BRICK_SUITE_SCALE_LDRAW


# ---------------------------------------------------------------------------
# Pure math - testable without bpy
# ---------------------------------------------------------------------------

def find_nearest_stud(new_part_verts, existing_verts, threshold=0.01):
    """Find the closest vertex pair between two parts for stud snapping."""
    best_dist   = float('inf')
    best_offset = None

    for nv in new_part_verts:
        for ev in existing_verts:
            dist = (nv - ev).length
            if dist < best_dist and dist < threshold:
                best_dist   = dist
                best_offset = ev - nv

    return best_offset


def cursor_to_ldraw(cursor_location, scale=BRICK_SUITE_SCALE_LDRAW):
    """Convert a Blender world-space cursor location to LDraw units."""
    x =  cursor_location.x / scale
    y = -cursor_location.z / scale
    z =  cursor_location.y / scale
    return mathutils.Vector((x, y, z))


def get_mesh_verts(obj):
    """Return world-space vertex positions for a mesh object."""
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def is_assembly_file(filepath):
    """Return True if the .dat file is a multi-part assembly/shortcut.

    Reads just the header lines (up to first geometry line) and checks for
    the !LDRAW_ORG Shortcut tag. Falls back to False on any read error.

    979.dat header contains:  0 !LDRAW_ORG Shortcut UPDATE 2010-02
    A plain part like 3001.dat contains: 0 !LDRAW_ORG Part UPDATE ...
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("0"):
                    low = line.lower()
                    if "shortcut" in low:
                        return True
                    if "!ldraw_org" in low:
                        # It has a type tag but not shortcut — stop looking
                        return False
                else:
                    # Hit geometry — no type tag found, treat as plain part
                    break
    except OSError:
        pass
    return False


# ---------------------------------------------------------------------------
# Import operator
# ---------------------------------------------------------------------------

class BRICKBUILDER_OT_ImportPart(bpy.types.Operator):
    """Import a LDraw part or assembly into the scene at the 3D cursor"""
    bl_idname = "brickbuilder.import_part"
    bl_label  = "Import Part"

    part_num:   bpy.props.StringProperty()
    color_code: bpy.props.StringProperty(default="14")

    def execute(self, context):
        from .thumbnails import get_part
        from . import get_api_key

        # --- resolve LDraw filename ---
        # For LDraw-index results the part_num IS the ldraw id already.
        # For Rebrickable results we look up the external LDraw id.
        part     = get_part(self.part_num, get_api_key())
        ldraw_id = part["ldraw_id"] if part else self.part_num
        filename = ldraw_id.lower() + ".dat"
        filepath = NetworkFileSystem.locate(filename)

        if filepath is None:
            self.report({'ERROR'}, f"Could not locate {filename}")
            return {'CANCELLED'}

        assembly = is_assembly_file(filepath)

        if assembly:
            root_obj = _do_import_assembly(filepath, self.color_code)
        else:
            root_obj = _do_import(filepath, self.color_code)

        if root_obj is None:
            self.report({'ERROR'}, f"Import failed for {filename}")
            return {'CANCELLED'}

        # Move to 3D cursor
        root_obj.location = context.scene.cursor.location

        # Tag for BrickSuite AutoRig detection
        root_obj["ldraw_filename"] = filename
        root_obj["ldraw_assembly"] = assembly

        # Stud snap (single parts only — assemblies are too complex)
        if not assembly:
            snap_target = _get_snap_target(context)
            if snap_target and snap_target != root_obj:
                offset = find_nearest_stud(
                    get_mesh_verts(root_obj),
                    get_mesh_verts(snap_target),
                )
                if offset:
                    root_obj.location += offset
                    self.report({'INFO'}, f"Snapped {self.part_num} to {snap_target.name}")
                    bpy.ops.object.select_all(action='DESELECT')
                    root_obj.select_set(True)
                    context.view_layer.objects.active = root_obj
                    return {'FINISHED'}

        label = "assembly" if assembly else "part"
        self.report({'INFO'}, f"Placed {label} {self.part_num} at cursor")

        bpy.ops.object.select_all(action='DESELECT')
        root_obj.select_set(True)
        context.view_layer.objects.active = root_obj

        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _do_import(filepath, color_code="14"):
    """Import a single .dat part. Returns the mesh object or None."""
    from .inc.blender_import import do_import
    from .inc.import_options  import ImportOptions

    ImportOptions.recalculate_normals = True
    ImportOptions.smooth_type         = 1      # auto_smooth
    ImportOptions.shade_smooth        = True
    ImportOptions.meta_step           = False
    ImportOptions.make_gaps           = False
    ImportOptions.parent_to_empty     = False

    return do_import(filepath, color_code=color_code)


def _do_import_assembly(filepath, color_code="14"):
    """Import a multi-part assembly (shortcut like 979.dat).

    Uses parent_to_empty=True so all sub-parts are grouped under one Empty.
    Returns the Empty object so the caller can move the whole assembly as a unit.

    If do_import doesn't create an empty (edge case), falls back to creating
    one ourselves and parenting all newly-added objects to it.
    """
    from .inc.blender_import import do_import
    from .inc.import_options  import ImportOptions
    from .inc               import ldraw_object as ldraw_obj_mod

    # Snapshot objects before import so we can find what was added
    before = set(bpy.data.objects)

    ImportOptions.recalculate_normals = True
    ImportOptions.smooth_type         = 1
    ImportOptions.shade_smooth        = True
    ImportOptions.meta_step           = False
    ImportOptions.make_gaps           = False
    ImportOptions.parent_to_empty     = True   # KEY: groups all sub-parts

    do_import(filepath, color_code=color_code)

    # Find the top-level Empty that was created by parent_to_empty
    top_empty = ldraw_obj_mod.top_empty
    if top_empty is not None:
        return top_empty

    # Fallback: find new objects added during import, create our own empty
    new_objs = [o for o in bpy.data.objects if o not in before]
    if not new_objs:
        return None

    # Check if one of them is already an empty
    for o in new_objs:
        if o.type == 'EMPTY':
            return o

    # Create a new empty and parent everything to it
    empty = bpy.data.objects.new(f"Assembly_{filepath.split('/')[-1]}", None)
    empty.empty_display_type = 'ARROWS'
    bpy.context.collection.objects.link(empty)
    for o in new_objs:
        if o.parent is None:
            o.parent = empty

    return empty


def _get_snap_target(context):
    """Return the active object if it's a mesh and not the object being placed."""
    obj = context.active_object
    if obj and obj.type == 'MESH' and obj.select_get():
        return obj
    return None


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = [BRICKBUILDER_OT_ImportPart]
