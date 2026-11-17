# D:\Antigravity\BlenderGuide\UV_Island_Target_Box_Addon\utils.py
import bpy
import bmesh
from mathutils import Vector


def get_active_mesh_and_bmesh(context):
    """Returns (obj, bm, uv_layer) for the active object in Edit mode, or None."""
    obj = context.active_object
    if not obj or obj.type != 'MESH' or obj.mode != 'EDIT':
        return None, None, None
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.verify()
    return obj, bm, uv_layer


def get_selected_uv_elements(context, bm, uv_layer):
    """Returns a list of loops that are selected in UV editor (considering sync mode and Blender versions)."""
    if not bm or not uv_layer:
        return []
    sync_mode = context.tool_settings.use_uv_select_sync
    selected_loops = []

    if sync_mode:
        for face in bm.faces:
            if face.select:
                selected_loops.extend(face.loops)
            else:
                for loop in face.loops:
                    if loop.vert.select or loop.edge.select:
                        selected_loops.append(loop)
    else:
        # In non-sync mode, only faces selected in 3D Viewport are active in the UV editor
        for face in bm.faces:
            if not face.select:
                continue
            for loop in face.loops:
                # Blender 5.0+ moved UV selection flags from BMLoopUV to BMLoop
                if hasattr(loop, "uv_select_vert"):
                    if loop.uv_select_vert or getattr(loop, "uv_select_edge", False):
                        selected_loops.append(loop)
                else:
                    # Blender <= 4.x
                    luv = loop[uv_layer]
                    if getattr(luv, "select", False) or getattr(luv, "select_edge", False):
                        selected_loops.append(loop)

        # Fallback: if 3D faces are selected but no UV sub-elements were explicitly selected,
        # use all loops of the 3D-selected faces.
        if not selected_loops:
            for face in bm.faces:
                if face.select:
                    selected_loops.extend(face.loops)

    return selected_loops


def get_uv_islands(bm, uv_layer, selected_loops=None, expand_to_island=True):
    """
    Extracts UV islands from the mesh.
    If selected_loops is provided:
      - If expand_to_island is True: returns all full connected islands that contain any of selected_loops.
      - If expand_to_island is False: returns islands restricted to the selected loops.
    Each island is returned as a list of loops.
    """
    import bpy
    sync_mode = getattr(bpy.context.tool_settings, "use_uv_select_sync", True) if getattr(bpy, "context", None) and hasattr(bpy.context, "tool_settings") else True
    all_faces = [f for f in bm.faces if f.select] if not sync_mode else bm.faces
    vert_uv_to_faces = {}
    for face in all_faces:
        for loop in face.loops:
            uv = loop[uv_layer].uv
            key = (loop.vert.index, round(uv.x, 4), round(uv.y, 4))
            vert_uv_to_faces.setdefault(key, []).append(face)

    # Build adjacency between faces sharing vertex & UV position
    adj = {face: set() for face in all_faces}
    for key, shared_faces in vert_uv_to_faces.items():
        if len(shared_faces) > 1:
            for i in range(len(shared_faces)):
                for j in range(i + 1, len(shared_faces)):
                    f1, f2 = shared_faces[i], shared_faces[j]
                    adj[f1].add(f2)
                    adj[f2].add(f1)

    # Find connected components (all islands)
    visited = set()
    all_islands_faces = []
    for face in all_faces:
        if face not in visited:
            comp = []
            queue = [face]
            visited.add(face)
            while queue:
                curr = queue.pop(0)
                comp.append(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            all_islands_faces.append(comp)

    if selected_loops is None:
        # Return all islands as lists of loops
        result = []
        for face_list in all_islands_faces:
            island_loops = []
            for face in face_list:
                island_loops.extend(face.loops)
            result.append(island_loops)
        return result

    selected_loop_set = set(selected_loops)
    selected_face_set = {loop.face for loop in selected_loops}

    result_islands = []
    for face_list in all_islands_faces:
        # Check if this island has any selected face
        island_face_set = set(face_list)
        common_faces = island_face_set.intersection(selected_face_set)
        if not common_faces:
            continue

        if expand_to_island:
            # Full island loops
            island_loops = []
            for face in face_list:
                island_loops.extend(face.loops)
            result_islands.append(island_loops)
        else:
            # Only selected loops within this island
            island_loops = [l for face in face_list for l in face.loops if l in selected_loop_set]
            if island_loops:
                result_islands.append(island_loops)

    return result_islands


def get_loops_bounds(loops, uv_layer):
    """Calculates the bounding box [min_u, min_v, max_u, max_v] of given loops."""
    if not loops:
        return 0.0, 0.0, 0.0, 0.0
    min_u = min(loop[uv_layer].uv.x for loop in loops)
    max_u = max(loop[uv_layer].uv.x for loop in loops)
    min_v = min(loop[uv_layer].uv.y for loop in loops)
    max_v = max(loop[uv_layer].uv.y for loop in loops)
    return min_u, min_v, max_u, max_v


def transform_uv_loops(
    loops,
    uv_layer,
    t_min_u,
    t_min_v,
    t_max_u,
    t_max_v,
    fit_mode='STRETCH',
    pad_u=0.0,
    pad_v=0.0,
    align_x='CENTER',
    align_y='CENTER',
    auto_rotate=False,
):
    """
    Fits given loops into the target bounding box [t_min_u, t_min_v, t_max_u, t_max_v].
    - fit_mode: 'STRETCH' (edge-to-edge on all 4 borders) or 'UNIFORM' (preserve aspect ratio).
    - pad_u, pad_v: padding margin subtracted inside the target box.
    - align_x: 'LEFT', 'CENTER', 'RIGHT' (for UNIFORM fit).
    - align_y: 'BOTTOM', 'CENTER', 'TOP' (for UNIFORM fit).
    """
    if not loops:
        return

    # Effective target bounds after padding
    eff_min_u = t_min_u + pad_u
    eff_max_u = t_max_u - pad_u
    eff_min_v = t_min_v + pad_v
    eff_max_v = t_max_v - pad_v

    target_w = eff_max_u - eff_min_u
    target_h = eff_max_v - eff_min_v

    if target_w <= 1e-7 or target_h <= 1e-7:
        return

    # Compute current bounds
    b_min_u, b_min_v, b_max_u, b_max_v = get_loops_bounds(loops, uv_layer)
    orig_w = b_max_u - b_min_u
    orig_h = b_max_v - b_min_v

    if orig_w <= 1e-7 or orig_h <= 1e-7:
        # Point/line degenerated: translate to center
        cx = (eff_min_u + eff_max_u) * 0.5
        cy = (eff_min_v + eff_max_v) * 0.5
        for loop in loops:
            loop[uv_layer].uv.x = cx
            loop[uv_layer].uv.y = cy
        return

    # Optional auto-rotate if aspect ratio orientation is opposite
    if auto_rotate:
        target_aspect = target_w / target_h
        orig_aspect = orig_w / orig_h
        if (target_aspect > 1.0 and orig_aspect < 1.0) or (target_aspect < 1.0 and orig_aspect > 1.0):
            # Rotate 90 degrees around center
            center_u = (b_min_u + b_max_u) * 0.5
            center_v = (b_min_v + b_max_v) * 0.5
            for loop in loops:
                uv = loop[uv_layer].uv
                rel_u = uv.x - center_u
                rel_v = uv.y - center_v
                uv.x = center_u - rel_v
                uv.y = center_v + rel_u
            # Recompute bounds after rotation
            b_min_u, b_min_v, b_max_u, b_max_v = get_loops_bounds(loops, uv_layer)
            orig_w = b_max_u - b_min_u
            orig_h = b_max_v - b_min_v

    if fit_mode == 'STRETCH':
        # Non-uniform scale to touch all 4 boundaries exactly
        scale_u = target_w / orig_w
        scale_v = target_h / orig_h
        for loop in loops:
            uv = loop[uv_layer].uv
            uv.x = eff_min_u + (uv.x - b_min_u) * scale_u
            uv.y = eff_min_v + (uv.y - b_min_v) * scale_v

    elif fit_mode == 'UNIFORM':
        # Uniform scale preserving original aspect ratio
        scale = min(target_w / orig_w, target_h / orig_h)
        scaled_w = orig_w * scale
        scaled_h = orig_h * scale

        extra_u = target_w - scaled_w
        extra_v = target_h - scaled_h

        if align_x == 'LEFT':
            offset_u = 0.0
        elif align_x == 'RIGHT':
            offset_u = extra_u
        else:  # 'CENTER'
            offset_u = extra_u * 0.5

        if align_y == 'BOTTOM':
            offset_v = 0.0
        elif align_y == 'TOP':
            offset_v = extra_v
        else:  # 'CENTER'
            offset_v = extra_v * 0.5

        start_u = eff_min_u + offset_u
        start_v = eff_min_v + offset_v

        for loop in loops:
            uv = loop[uv_layer].uv
            uv.x = start_u + (uv.x - b_min_u) * scale
            uv.y = start_v + (uv.y - b_min_v) * scale
