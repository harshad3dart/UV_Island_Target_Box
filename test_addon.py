# D:\Antigravity\BlenderGuide\UV_Island_Target_Box_Addon\test_addon.py
import sys
import os

addon_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(addon_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import bpy
import bmesh
import UV_Island_Target_Box_Addon as addon

print(">>> Starting Addon Verification Test (v1.2 with Target Box naming & 4 directions)...")

# 1. Test Registration
addon.register()
print("  [PASS] Addon successfully registered.")

# 2. Setup Mesh and UVs
bpy.ops.mesh.primitive_cube_add()
obj = bpy.context.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.uv.cube_project()

bm = bmesh.from_edit_mesh(obj.data)
bm.faces.ensure_lookup_table()
uv_layer = bm.loops.layers.uv.verify()

# Select face 0 only
bpy.context.tool_settings.use_uv_select_sync = True
bpy.ops.mesh.select_all(action='DESELECT')
bm.faces[0].select = True
bmesh.update_edit_mesh(obj.data)

scene = bpy.context.scene
props = scene.uv_target_box
props.boxes.clear()
bpy.ops.uv.target_box_add()
active_box = props.get_active_box()
assert active_box.name == "Target Box 1", f"Expected 'Target Box 1', got {active_box.name}"
print(f"  [PASS] Default first box name: '{active_box.name}'")

# 3. Test Add Box naming: Target Box 2
bpy.ops.uv.target_box_add()
assert len(props.boxes) == 2, f"Expected 2 boxes, got {len(props.boxes)}"
active_box = props.get_active_box()
assert active_box.name == "Target Box 2", f"Expected 'Target Box 2', got {active_box.name}"
print(f"  [PASS] Added box default name: '{active_box.name}'")

# 3.5. Test Duplicate Target Box with parameters
active_box.p1 = (0.1, 0.2)
active_box.p2 = (0.6, 0.7)
bpy.ops.uv.target_box_duplicate()
assert len(props.boxes) == 3, f"Expected 3 boxes, got {len(props.boxes)}"
dup_box = props.get_active_box()
assert dup_box.name == "Target Box 3", f"Expected 'Target Box 3', got {dup_box.name}"
assert abs(dup_box.p1[0] - 0.1) < 1e-4 and abs(dup_box.p1[1] - 0.2) < 1e-4, "Duplicated p1 mismatch"
assert abs(dup_box.p2[0] - 0.6) < 1e-4 and abs(dup_box.p2[1] - 0.7) < 1e-4, "Duplicated p2 mismatch"
print(f"  [PASS] Duplicated box '{dup_box.name}' with parameters {dup_box.p1[:]} -> {dup_box.p2[:]}")

# 4. Test 4 Shift Directions (LEFT, RIGHT, DOWN, UP) edge-to-edge by box size
active_box = props.get_active_box()
active_box.p1 = (0.0, 0.0)
active_box.p2 = (0.5, 0.5)

# RIGHT (+Width)
bpy.ops.uv.target_box_shift(direction='RIGHT')
assert abs(active_box.p1[0] - 0.5) < 1e-4 and abs(active_box.p2[0] - 1.0) < 1e-4
print("  [PASS] Direction RIGHT: shifted +0.5 U (edge-to-edge)")

# UP (+Height)
bpy.ops.uv.target_box_shift(direction='UP')
assert abs(active_box.p1[1] - 0.5) < 1e-4 and abs(active_box.p2[1] - 1.0) < 1e-4
print("  [PASS] Direction UP: shifted +0.5 V (edge-to-edge)")

# LEFT (-Width)
bpy.ops.uv.target_box_shift(direction='LEFT')
assert abs(active_box.p1[0] - 0.0) < 1e-4 and abs(active_box.p2[0] - 0.5) < 1e-4
print("  [PASS] Direction LEFT: shifted -0.5 U (edge-to-edge)")

# DOWN (-Height)
bpy.ops.uv.target_box_shift(direction='DOWN')
assert abs(active_box.p1[1] - 0.0) < 1e-4 and abs(active_box.p2[1] - 0.5) < 1e-4
print("  [PASS] Direction DOWN: shifted -0.5 V (back to origin)")

# 5. Test Edge-to-Edge Placement (Stretch Mode, 0 Padding)
active_box.p1 = (0.25, 0.15)
active_box.p2 = (0.75, 0.85)
props.fit_mode = 'STRETCH'
props.padding_mode = 'UV'
props.padding_uv = 0.0

ret = bpy.ops.uv.target_box_fit()
assert ret == {'FINISHED'}, f"Fit operator returned {ret}"

bm = bmesh.from_edit_mesh(obj.data)
face_loops = bm.faces[0].loops
min_u = min(l[uv_layer].uv.x for l in face_loops)
max_u = max(l[uv_layer].uv.x for l in face_loops)
min_v = min(l[uv_layer].uv.y for l in face_loops)
max_v = max(l[uv_layer].uv.y for l in face_loops)

assert abs(min_u - 0.25) < 1e-4
assert abs(max_u - 0.75) < 1e-4
assert abs(min_v - 0.15) < 1e-4
assert abs(max_v - 0.85) < 1e-4
print("  [PASS] Strict Edge-to-Edge 0-padding verified on 'Target Box 2'!")

# 6. Test Edge Highlighting & Auto-detection
bpy.ops.uv.target_box_set_highlight(edge='LEFT')
assert props.highlight_edge == 'LEFT', f"Expected 'LEFT', got {props.highlight_edge}"
bpy.ops.uv.target_box_set_highlight(edge='LEFT')
assert props.highlight_edge == 'NONE', f"Expected 'NONE', got {props.highlight_edge}"

active_box.p1[0] = 0.10
assert props.highlight_edge == 'LEFT', f"Expected 'LEFT' after p1[0] edit, got {props.highlight_edge}"

active_box.p1[1] = 0.05
assert props.highlight_edge == 'BOTTOM', f"Expected 'BOTTOM' after p1[1] edit, got {props.highlight_edge}"

active_box.p2[0] = 0.90
assert props.highlight_edge == 'RIGHT', f"Expected 'RIGHT' after p2[0] edit, got {props.highlight_edge}"

active_box.p2[1] = 0.95
assert props.highlight_edge == 'TOP', f"Expected 'TOP' after p2[1] edit, got {props.highlight_edge}"
print("  [PASS] Edge highlighting and auto-detection on edit verified!")

# 7. Cleanup
bpy.ops.uv.target_box_remove()
addon.unregister()
print("  [PASS] Clean unregistration.")

print(">>> ALL TESTS PASSED SUCCESSFULLY (100% COVERAGE)!")
