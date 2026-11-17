# D:\Antigravity\BlenderGuide\UV_Island_Target_Box_Addon\__init__.py
bl_info = {
    "name": "UV Island Target Box",
    "author": "Antigravity",
    "version": (1, 11, 1),
    "blender": (4, 0, 0),
    "location": "UV Editor > Sidebar (N) > Target Box",
    "description": "Create custom target bounding box presets and place UV islands edge-to-edge with optional padding",
    "warning": "",
    "doc_url": "",
    "category": "UV",
}

if "bpy" in locals():
    import importlib
    if "utils" in locals():
        importlib.reload(utils)
    if "properties" in locals():
        importlib.reload(properties)
    if "operators" in locals():
        importlib.reload(operators)
    if "draw" in locals():
        importlib.reload(draw)
    if "ui" in locals():
        importlib.reload(ui)
else:
    from . import utils
    from . import properties
    from . import operators
    from . import draw
    from . import ui

import bpy

classes = (
    operators.UV_OT_target_box_fit,
    operators.UV_OT_target_box_add,
    operators.UV_OT_target_box_remove,
    operators.UV_OT_target_box_duplicate,
    operators.UV_OT_target_box_from_selection,
    operators.UV_OT_target_box_reset,
    operators.UV_OT_target_box_shift,
    operators.UV_OT_target_box_draw,
    operators.UV_OT_target_box_set_highlight,
    ui.UV_UL_target_boxes,
    ui.IMAGE_PT_uv_target_box,
)


def register():
    properties.register()
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)
    draw.register_draw_handler()


def unregister():
    draw.unregister_draw_handler()
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    properties.unregister()


if __name__ == "__main__":
    register()
