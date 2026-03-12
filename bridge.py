# BrickBuilder/bridge.py
# Handoff from BrickBuilder to BrickSuite.
# Detects whether BrickSuite is installed, selects all placed LDraw parts,
# and calls normalize + rig in one click.

import bpy


def bricksuite_available():
    """Return True if BrickSuite operators are registered in Blender."""
    return (hasattr(bpy.ops, 'brick') and
            hasattr(bpy.ops.brick, 'normalize_scale') and
            hasattr(bpy.ops, 'auto') and
            hasattr(bpy.ops.auto, 'rig'))


def get_placed_parts(context):
    """Return all mesh objects in the scene that were placed by BrickBuilder.

    BrickBuilder sets ldraw_filename on every imported part so we can
    identify them reliably even if the user renamed the objects.
    """
    return [
        obj for obj in context.scene.objects
        if obj.type == 'MESH' and obj.get('ldraw_filename')
    ]


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class BRICKBUILDER_OT_RigWithBrickSuite(bpy.types.Operator):
    """Select all placed LDraw parts and rig them with BrickSuite"""
    bl_idname = "brickbuilder.rig_with_bricksuite"
    bl_label  = "Rig with BrickSuite"

    @classmethod
    def poll(cls, context):
        return bricksuite_available()

    def execute(self, context):
        parts = get_placed_parts(context)
        if not parts:
            self.report({'WARNING'}, "No BrickBuilder parts found in scene")
            return {'CANCELLED'}

        bpy.ops.object.select_all(action='DESELECT')
        for obj in parts:
            obj.select_set(True)
        context.view_layer.objects.active = parts[0]

        bpy.ops.brick.normalize_scale()
        bpy.ops.auto.rig()

        self.report({'INFO'}, f"Rigged {len(parts)} parts with BrickSuite")
        return {'FINISHED'}


class BRICKBUILDER_OT_SelectPlacedParts(bpy.types.Operator):
    """Select all parts placed by BrickBuilder"""
    bl_idname = "brickbuilder.select_placed"
    bl_label  = "Select Placed Parts"

    def execute(self, context):
        parts = get_placed_parts(context)
        if not parts:
            self.report({'WARNING'}, "No BrickBuilder parts found in scene")
            return {'CANCELLED'}

        bpy.ops.object.select_all(action='DESELECT')
        for obj in parts:
            obj.select_set(True)
        context.view_layer.objects.active = parts[0]

        self.report({'INFO'}, f"Selected {len(parts)} parts")
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Panel addition - adds bridge buttons to BrickSuite's existing panel
# ---------------------------------------------------------------------------

class BRICKBUILDER_PT_Bridge(bpy.types.Panel):
    bl_label       = "BrickBuilder"
    bl_idname      = "BRICKBUILDER_PT_BRIDGE"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category    = 'Brick Suite'
    bl_order       = 11

    def draw(self, context):
        layout = self.layout
        col    = layout.column(align=True)

        col.operator("brickbuilder.select_placed", icon='RESTRICT_SELECT_OFF')

        if bricksuite_available():
            col.operator("brickbuilder.rig_with_bricksuite", icon='ARMATURE_DATA')
        else:
            col.label(text="BrickSuite not installed", icon='ERROR')


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = [
    BRICKBUILDER_OT_RigWithBrickSuite,
    BRICKBUILDER_OT_SelectPlacedParts,
    BRICKBUILDER_PT_Bridge,
]
