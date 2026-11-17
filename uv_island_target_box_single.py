# D:\Antigravity\BlenderGuide\UV_Island_Target_Box_Addon\uv_island_target_box_single.py



bl_info = {



    "name": "UV Island Target Box",



    "author": "Antigravity",



    "version": (1, 11, 1),



    "blender": (4, 0, 0),



    "location": "UV Editor > Sidebar (N) > Target Box",



    "description": "Create custom target bounding box presets and place UV islands edge-to-edge with optional padding",



    "category": "UV",



}







import bpy



import bmesh



import blf



import gpu



import math



from mathutils import Vector







# ==============================================================================



# UTILS



# ==============================================================================



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







# ==============================================================================



# PROPERTIES



# ==============================================================================











def on_p1_update(self, context):



    try:



        scene = getattr(context, "scene", None)



        if not scene:



            return



        props = getattr(scene, "uv_target_box", None)



        if props:



            p0_prev = self.get("_prev_p1_0")



            p1_prev = self.get("_prev_p1_1")



            if p0_prev is not None and abs(self.p1[0] - p0_prev) > 1e-5:



                props.highlight_edge = 'LEFT'



            elif p1_prev is not None and abs(self.p1[1] - p1_prev) > 1e-5:



                props.highlight_edge = 'BOTTOM'



            self["_prev_p1_0"] = self.p1[0]



            self["_prev_p1_1"] = self.p1[1]



        area = getattr(context, "area", None)



        if area:



            area.tag_redraw()



    except Exception:



        pass











def on_p2_update(self, context):



    try:



        scene = getattr(context, "scene", None)



        if not scene:



            return



        props = getattr(scene, "uv_target_box", None)



        if props:



            p0_prev = self.get("_prev_p2_0")



            p1_prev = self.get("_prev_p2_1")



            if p0_prev is not None and abs(self.p2[0] - p0_prev) > 1e-5:



                props.highlight_edge = 'RIGHT'



            elif p1_prev is not None and abs(self.p2[1] - p1_prev) > 1e-5:



                props.highlight_edge = 'TOP'



            self["_prev_p2_0"] = self.p2[0]



            self["_prev_p2_1"] = self.p2[1]



        area = getattr(context, "area", None)



        if area:



            area.tag_redraw()



    except Exception:



        pass











class UVTargetBoxItem(bpy.types.PropertyGroup):



    """A single custom target bounding box preset."""



    name: bpy.props.StringProperty(



        name="Box Name",



        description="Name identifier for this target box preset",



        default="Target Box 1",



    )







    p1: bpy.props.FloatVectorProperty(



        name="P1 (Min: Left & Bottom)",



        description="First corner of target bounding box (U = Left edge, V = Bottom edge)",



        size=2,



        default=(0.0, 0.0),



        precision=4,



        step=1,



        update=on_p1_update,



    )







    p2: bpy.props.FloatVectorProperty(



        name="P2 (Max: Right & Top)",



        description="Opposite corner of target bounding box (U = Right edge, V = Top edge)",



        size=2,



        default=(1.0, 1.0),



        precision=4,



        step=1,



        update=on_p2_update,



    )











def on_color_update(self, context):



    try:



        area = getattr(context, "area", None)



        if area:



            area.tag_redraw()



    except Exception:



        pass











class UVTargetBoxProperties(bpy.types.PropertyGroup):



    """Main addon properties stored on the scene."""







    boxes: bpy.props.CollectionProperty(type=UVTargetBoxItem)



    active_box_index: bpy.props.IntProperty(



        name="Active Box Index",



        description="Index of the currently active target box",



        default=0,



        min=0,



    )







    show_overlay: bpy.props.BoolProperty(



        name="Show Target Box",



        description="Display target box overlay inside the UV Editor viewport",



        default=True,



    )







    show_all_boxes: bpy.props.BoolProperty(



        name="Show Inactive Boxes",



        description="Display other saved target boxes as subtle outlines",



        default=True,



    )







    highlight_edge: bpy.props.EnumProperty(



        name="Highlight Line",



        description="Select an edge line of the target box to highlight in the UV viewport",



        items=[



            ('NONE', "Off", "No line highlighted"),



            ('LEFT', "Left", "Highlight Left (P1 U) edge"),



            ('BOTTOM', "Bottom", "Highlight Bottom (P1 V) edge"),



            ('RIGHT', "Right", "Highlight Right (P2 U) edge"),



            ('TOP', "Top", "Highlight Top (P2 V) edge"),



            ('ALL', "All", "Highlight all 4 edges"),



        ],



        default='NONE',



    )







    show_edge_labels: bpy.props.BoolProperty(



        name="Show Edge Labels",



        description="Display Left, Bottom, Right, Top labels directly on the target box in viewport",



        default=True,



    )







    color_left: bpy.props.FloatVectorProperty(



        name="Left Edge Color",



        description="Color for the Left edge (P1 U)",



        subtype='COLOR',



        size=3,



        default=(0.0, 0.95, 1.0),



        min=0.0,



        max=1.0,



        update=on_color_update,



    )







    color_bottom: bpy.props.FloatVectorProperty(



        name="Bottom Edge Color",



        description="Color for the Bottom edge (P1 V)",



        subtype='COLOR',



        size=3,



        default=(0.15, 1.0, 0.4),



        min=0.0,



        max=1.0,



        update=on_color_update,



    )







    color_right: bpy.props.FloatVectorProperty(



        name="Right Edge Color",



        description="Color for the Right edge (P2 U)",



        subtype='COLOR',



        size=3,



        default=(1.0, 0.6, 0.15),



        min=0.0,



        max=1.0,



        update=on_color_update,



    )







    color_top: bpy.props.FloatVectorProperty(



        name="Top Edge Color",



        description="Color for the Top edge (P2 V)",



        subtype='COLOR',



        size=3,



        default=(1.0, 0.3, 0.7),



        min=0.0,



        max=1.0,



        update=on_color_update,



    )







    fit_mode: bpy.props.EnumProperty(



        name="Fit Mode",



        description="Method used to scale the UV island into the target box",



        items=[



            ('STRETCH', "Stretch to Fill", "Touch all 4 edges of the target box (edge-to-edge)"),



            ('UNIFORM', "Fit Uniform", "Preserve aspect ratio, touching boundary on dominant axis"),



        ],



        default='STRETCH',



    )







    align_horizontal: bpy.props.EnumProperty(



        name="Align X",



        description="Horizontal alignment when using Fit Uniform",



        items=[



            ('LEFT', "Left", "Align island to Left edge"),



            ('CENTER', "Center", "Center island horizontally"),



            ('RIGHT', "Right", "Align island to Right edge"),



        ],



        default='CENTER',



    )







    align_vertical: bpy.props.EnumProperty(



        name="Align Y",



        description="Vertical alignment when using Fit Uniform",



        items=[



            ('BOTTOM', "Bottom", "Align island to Bottom edge"),



            ('CENTER', "Center", "Center island vertically"),



            ('TOP', "Top", "Align island to Top edge"),



        ],



        default='CENTER',



    )







    padding_mode: bpy.props.EnumProperty(



        name="Padding Unit",



        description="Padding unit for inner margin",



        items=[



            ('UV', "UV Space", "Padding specified in UV units (0.0 to 1.0)"),



            ('PIXEL', "Pixels", "Padding specified in texture pixels"),



        ],



        default='UV',



    )







    padding_uv: bpy.props.FloatProperty(



        name="Padding (UV)",



        description="Padding margin around island inside the box (0.0 = strict edge-to-edge)",



        default=0.0,



        min=0.0,



        max=0.5,



        step=0.01,



        precision=4,



    )







    padding_pixel: bpy.props.IntProperty(



        name="Padding (px)",



        description="Padding margin in pixels inside the box (0 = strict edge-to-edge)",



        default=0,



        min=0,



        max=1024,



    )







    texture_resolution: bpy.props.IntProperty(



        name="Fallback Res",



        description="Texture resolution for pixel padding calculation if no image is open",



        default=1024,



        min=64,



        max=16384,



    )







    auto_rotate: bpy.props.BoolProperty(



        name="Auto Orient",



        description="Rotate island 90 degrees if it better matches target box aspect ratio",



        default=False,



    )







    move_selection_with_tile: bpy.props.BoolProperty(



        name="Move UVs with Box Shift",



        description="When shifting the target box with arrow buttons, also move the selected UVs",



        default=False,



    )







    def get_active_box(self):



        """Returns the active UVTargetBoxItem (strictly read-only)."""



        if len(self.boxes) == 0:



            return None



        idx = max(0, min(self.active_box_index, len(self.boxes) - 1))



        return self.boxes[idx]











@bpy.app.handlers.persistent



def on_load_post(dummy=None):



    for scene in bpy.data.scenes:



        props = getattr(scene, "uv_target_box", None)



        if not props:



            continue



        if len(props.boxes) == 0:



            box = props.boxes.add()



            box.name = "Target Box 1"



            box.p1 = (0.0, 0.0)



            box.p2 = (1.0, 1.0)



            props.active_box_index = 0



        else:



            for i, b in enumerate(props.boxes):



                if not b.name or b.name.strip() == "" or b.name.startswith("Box "):



                    b.name = f"Target Box {i + 1}"















# ==============================================================================



# DRAW OVERLAY



# ==============================================================================







_draw_handler = None











def get_shader():



    """Safely retrieves a 2D uniform color shader."""



    import gpu



    for name in ('UNIFORM_COLOR', '2D_UNIFORM_COLOR'):



        try:



            return gpu.shader.from_builtin(name)



        except Exception:



            continue



    return None











def draw_thick_line_quad(shader, pt_a, pt_b, color, thickness=4.0):



    """Draws a thick line as a quad (two triangles) for consistent rendering across all GPU drivers."""



    import math



    from gpu_extras.batch import batch_for_shader







    dx = pt_b[0] - pt_a[0]



    dy = pt_b[1] - pt_a[1]



    dist = math.hypot(dx, dy)



    if dist < 1e-4:



        return







    nx = -dy / dist * (thickness * 0.5)



    ny = dx / dist * (thickness * 0.5)







    q0 = (pt_a[0] + nx, pt_a[1] + ny)



    q1 = (pt_b[0] + nx, pt_b[1] + ny)



    q2 = (pt_b[0] - nx, pt_b[1] - ny)



    q3 = (pt_a[0] - nx, pt_a[1] - ny)







    tris = [q0, q1, q2, q0, q2, q3]



    try:



        batch = batch_for_shader(shader, 'TRIS', {"pos": tris})



        shader.bind()



        shader.uniform_float("color", color)



        batch.draw(shader)



    except Exception:



        pass











def draw_box_rect(shader, p0, p1, p2, p3, fill_color=None, border_color=None, line_width=1.5):



    """Draws a rectangle with optional fill and border."""



    import gpu



    from gpu_extras.batch import batch_for_shader







    # 1. Fill



    if fill_color:



        tris = [p0, p1, p2, p0, p2, p3]



        try:



            gpu.state.blend_set('ALPHA')



            batch_fill = batch_for_shader(shader, 'TRIS', {"pos": tris})



            shader.bind()



            shader.uniform_float("color", fill_color)



            batch_fill.draw(shader)



        except Exception:



            pass







    # 2. Border



    if border_color:



        lines = [p0, p1, p1, p2, p2, p3, p3, p0]



        try:



            gpu.state.blend_set('ALPHA')



            batch_lines = batch_for_shader(shader, 'LINES', {"pos": lines})



            shader.bind()



            shader.uniform_float("color", border_color)



            try:



                gpu.state.line_width_set(line_width)



            except Exception:



                pass



            batch_lines.draw(shader)



        except Exception:



            pass











def draw_target_box_callback():



    if bpy.app.background:



        return







    context = bpy.context



    scene = getattr(context, "scene", None)



    if not scene:



        return







    props = getattr(scene, "uv_target_box", None)



    if not props or not props.show_overlay:



        return







    space = context.space_data



    if not space or space.type != 'IMAGE_EDITOR' or getattr(space, "mode", "") != 'UV':



        return







    region = context.region



    if not region or not hasattr(region, "view2d"):



        return







    import gpu



    from gpu_extras.batch import batch_for_shader







    shader = get_shader()



    if not shader:



        return







    v2r = region.view2d.view_to_region



    active_box = props.get_active_box()







    # Enable Alpha blending



    try:



        gpu.state.blend_set('ALPHA')



    except Exception:



        pass







    # 1. Draw inactive boxes (if enabled)



    if props.show_all_boxes and len(props.boxes) > 1:



        for i, box in enumerate(props.boxes):



            if i == props.active_box_index:



                continue



            bu_min = min(box.p1[0], box.p2[0])



            bu_max = max(box.p1[0], box.p2[0])



            bv_min = min(box.p1[1], box.p2[1])



            bv_max = max(box.p1[1], box.p2[1])



            bp0 = v2r(bu_min, bv_min, clip=False)



            bp1 = v2r(bu_max, bv_min, clip=False)



            bp2 = v2r(bu_max, bv_max, clip=False)



            bp3 = v2r(bu_min, bv_max, clip=False)







            # Faint subtle border & fill for inactive boxes



            draw_box_rect(



                shader, bp0, bp1, bp2, bp3,



                fill_color=(0.3, 0.5, 0.8, 0.02),



                border_color=(0.4, 0.65, 0.9, 0.45),



                line_width=1.0,



            )



            # Inactive box label



            try:



                font_id = 0



                blf.size(font_id, 10)



                blf.color(font_id, 0.5, 0.7, 0.9, 0.6)



                blf.position(font_id, min(bp0[0], bp3[0]) + 4, max(bp2[1], bp3[1]) + 4, 0)



                blf.draw(font_id, box.name)



            except Exception:



                pass







    # 2. Draw active box



    u_min = min(active_box.p1[0], active_box.p2[0])



    u_max = max(active_box.p1[0], active_box.p2[0])



    v_min = min(active_box.p1[1], active_box.p2[1])



    v_max = max(active_box.p1[1], active_box.p2[1])







    p0 = v2r(u_min, v_min, clip=False)



    p1 = v2r(u_max, v_min, clip=False)



    p2 = v2r(u_max, v_max, clip=False)



    p3 = v2r(u_min, v_max, clip=False)







    # Active Fill (5% opacity fill, borders handled by colored edge segments)



    draw_box_rect(



        shader, p0, p1, p2, p3,



        fill_color=(1.0, 0.78, 0.05, 0.05),



        border_color=None,



    )







    # 3. Draw Edge Outlines & Highlighted Edge(s) using Box Boundary Edges Colors



    c_l = getattr(props, "color_left", (0.0, 0.95, 1.0))



    c_b = getattr(props, "color_bottom", (0.15, 1.0, 0.4))



    c_r = getattr(props, "color_right", (1.0, 0.6, 0.15))



    c_t = getattr(props, "color_top", (1.0, 0.3, 0.7))







    col_l = (c_l[0], c_l[1], c_l[2], 1.0)



    col_b = (c_b[0], c_b[1], c_b[2], 1.0)



    col_r = (c_r[0], c_r[1], c_r[2], 1.0)



    col_t = (c_t[0], c_t[1], c_t[2], 1.0)







    # Base colored border segments



    draw_thick_line_quad(shader, p0, p3, col_l, thickness=3.0)



    draw_thick_line_quad(shader, p0, p1, col_b, thickness=3.0)



    draw_thick_line_quad(shader, p1, p2, col_r, thickness=3.0)



    draw_thick_line_quad(shader, p3, p2, col_t, thickness=3.0)







    hl = getattr(props, "highlight_edge", 'NONE')



    edge_defs = [



        ('LEFT', p0, p3, col_l, f"◄ Left Edge (P1 U = {u_min:.4f})"),



        ('BOTTOM', p0, p1, col_b, f"▼ Bottom Edge (P1 V = {v_min:.4f})"),



        ('RIGHT', p1, p2, col_r, f"Right Edge (P2 U = {u_max:.4f}) ►"),



        ('TOP', p3, p2, col_t, f"▲ Top Edge (P2 V = {v_max:.4f})"),



    ]







    active_labels = []



    for key, pt_a, pt_b, col, lbl in edge_defs:



        if hl in (key, 'ALL'):



            draw_thick_line_quad(shader, pt_a, pt_b, (col[0], col[1], col[2], 0.4), thickness=8.0)



            draw_thick_line_quad(shader, pt_a, pt_b, col, thickness=5.0)



            active_labels.append((key, pt_a, pt_b, col, lbl))







    # Corner handles (8x8 px) drawn on top of border edges



    h = 4



    handle_verts = []



    for px, py in (p0, p1, p2, p3):



        handle_verts.extend([



            (px - h, py - h), (px + h, py - h), (px + h, py + h),



            (px - h, py - h), (px + h, py + h), (px - h, py + h)



        ])



    try:



        gpu.state.blend_set('ALPHA')



        batch_handles = batch_for_shader(shader, 'TRIS', {"pos": handle_verts})



        shader.bind()



        shader.uniform_float("color", (1.0, 1.0, 1.0, 0.95))



        batch_handles.draw(shader)



    except Exception:



        pass







    # 4. Inner boundary preview if padding is active



    pad_u = 0.0



    pad_v = 0.0



    if props.padding_mode == 'UV':



        pad_u = props.padding_uv



        pad_v = props.padding_uv



    elif props.padding_mode == 'PIXEL' and props.padding_pixel > 0:



        img_w, img_h = 1024, 1024



        if space.image and space.image.size[0] > 0 and space.image.size[1] > 0:



            img_w, img_h = space.image.size[0], space.image.size[1]



        else:



            img_w, img_h = props.texture_resolution, props.texture_resolution



        pad_u = props.padding_pixel / img_w



        pad_v = props.padding_pixel / img_h







    if (pad_u > 0.0 or pad_v > 0.0) and (u_max - u_min > 2 * pad_u) and (v_max - v_min > 2 * pad_v):



        ip0 = v2r(u_min + pad_u, v_min + pad_v, clip=False)



        ip1 = v2r(u_max - pad_u, v_min + pad_v, clip=False)



        ip2 = v2r(u_max - pad_u, v_max - pad_v, clip=False)



        ip3 = v2r(u_min + pad_u, v_max - pad_v, clip=False)



        draw_box_rect(



            shader, ip0, ip1, ip2, ip3,



            fill_color=None,



            border_color=(0.2, 0.85, 1.0, 0.75),



            line_width=1.0,



        )







    # Restore state



    try:



        gpu.state.blend_set('NONE')



        gpu.state.line_width_set(1.0)



    except Exception:



        pass







    # 5. Dimension & Name text readout and Edge Labels



    try:



        font_id = 0







        # Draw floating labels for active highlighted edges



        for key, pt_a, pt_b, col, lbl in active_labels:



            blf.size(font_id, 11)



            blf.color(font_id, col[0], col[1], col[2], 1.0)



            mid_x = (pt_a[0] + pt_b[0]) * 0.5



            mid_y = (pt_a[1] + pt_b[1]) * 0.5



            if key == 'LEFT':



                blf.position(font_id, pt_a[0] - 180, mid_y - 5, 0)



            elif key == 'RIGHT':



                blf.position(font_id, pt_a[0] + 12, mid_y - 5, 0)



            elif key == 'BOTTOM':



                blf.position(font_id, mid_x - 90, pt_a[1] - 20, 0)



            elif key == 'TOP':



                blf.position(font_id, mid_x - 70, pt_a[1] + 18, 0)



            blf.draw(font_id, lbl)







        # Draw subtle edge & corner indicators if enabled and not already highlighted



        if getattr(props, "show_edge_labels", True):



            blf.size(font_id, 10)



            # Corner markers: P1 at p0 (Bottom-Left), P2 at p2 (Top-Right)



            blf.color(font_id, 0.2, 0.9, 1.0, 0.9)



            blf.position(font_id, p0[0] - 24, p0[1] - 14, 0)



            blf.draw(font_id, "[P1]")







            blf.color(font_id, 1.0, 0.65, 0.2, 0.9)



            blf.position(font_id, p2[0] + 6, p2[1] + 4, 0)



            blf.draw(font_id, "[P2]")







            # Edge indicators if no specific edge is highlighted



            if hl == 'NONE':



                blf.color(font_id, 1.0, 1.0, 1.0, 0.5)



                # Left



                blf.position(font_id, p0[0] - 48, (p0[1] + p3[1]) * 0.5 - 5, 0)



                blf.draw(font_id, "P1 Left")



                # Bottom



                blf.position(font_id, (p0[0] + p1[0]) * 0.5 - 28, p0[1] - 14, 0)



                blf.draw(font_id, "P1 Bottom")



                # Right



                blf.position(font_id, p1[0] + 8, (p1[1] + p2[1]) * 0.5 - 5, 0)



                blf.draw(font_id, "P2 Right")



                # Top



                blf.position(font_id, (p3[0] + p2[0]) * 0.5 - 20, p2[1] + 6, 0)



                blf.draw(font_id, "P2 Top")



    except Exception:



        pass











def register_draw_handler():



    global _draw_handler



    if _draw_handler is None and not bpy.app.background:



        _draw_handler = bpy.types.SpaceImageEditor.draw_handler_add(



            draw_target_box_callback, (), 'WINDOW', 'POST_PIXEL'



        )











def unregister_draw_handler():



    global _draw_handler



    if _draw_handler is not None:



        try:



            bpy.types.SpaceImageEditor.draw_handler_remove(_draw_handler, 'WINDOW')



        except Exception:



            pass



        _draw_handler = None







# ==============================================================================



# OPERATORS



# ==============================================================================











class UV_OT_target_box_fit(bpy.types.Operator):



    """Place and fit selected UV island(s) edge-to-edge into the active target bounding box"""



    bl_idname = "uv.target_box_fit"



    bl_label = "Fit Island to Target Box"



    bl_options = {'REGISTER', 'UNDO'}







    @classmethod



    def poll(cls, context):



        obj = context.active_object



        return obj and obj.type == 'MESH' and obj.mode == 'EDIT'







    def execute(self, context):



        props = context.scene.uv_target_box



        active_box = props.get_active_box()



        obj, bm, uv_layer = get_active_mesh_and_bmesh(context)



        if not obj or not bm or not uv_layer:



            self.report({'ERROR'}, "Active object must be a Mesh in Edit Mode.")



            return {'CANCELLED'}







        # Calculate normalized target bounds



        u_min = min(active_box.p1[0], active_box.p2[0])



        u_max = max(active_box.p1[0], active_box.p2[0])



        v_min = min(active_box.p1[1], active_box.p2[1])



        v_max = max(active_box.p1[1], active_box.p2[1])







        target_w = u_max - u_min



        target_h = v_max - v_min







        if target_w <= 1e-6 or target_h <= 1e-6:



            self.report({'ERROR'}, f"Target box '{active_box.name}' has zero width or height.")



            return {'CANCELLED'}







        # Calculate uniform padding



        pad_u = 0.0



        pad_v = 0.0



        if props.padding_mode == 'UV':



            pad_u = props.padding_uv



            pad_v = props.padding_uv



        elif props.padding_mode == 'PIXEL' and props.padding_pixel > 0:



            img_w, img_h = 1024, 1024



            space = context.space_data



            if space and space.type == 'IMAGE_EDITOR' and space.image and space.image.size[0] > 0:



                img_w, img_h = space.image.size[0], space.image.size[1]



            else:



                img_w, img_h = props.texture_resolution, props.texture_resolution



            pad_u = props.padding_pixel / img_w



            pad_v = props.padding_pixel / img_h







        # Check effective bounds with padding



        if (target_w - 2 * pad_u <= 1e-6) or (target_h - 2 * pad_v <= 1e-6):



            self.report({'WARNING'}, "Padding is too large for the current target box size.")



            pad_u = max(0.0, (target_w - 1e-5) * 0.5)



            pad_v = max(0.0, (target_h - 1e-5) * 0.5)







        # Get selected UV elements



        selected_loops = get_selected_uv_elements(context, bm, uv_layer)



        if not selected_loops:



            self.report({'WARNING'}, "No UV faces or vertices are currently selected.")



            return {'CANCELLED'}







        # Extract islands (combined as one unit)



        islands = get_uv_islands(bm, uv_layer, selected_loops, expand_to_island=True)



        if not islands:



            self.report({'WARNING'}, "No UV islands identified in selection.")



            return {'CANCELLED'}







        # Combine all selected loops to fit as one single bounding unit



        all_loops = [loop for island in islands for loop in island]



        transform_uv_loops(



            all_loops,



            uv_layer,



            u_min,



            v_min,



            u_max,



            v_max,



            fit_mode=props.fit_mode,



            pad_u=pad_u,



            pad_v=pad_v,



            align_x=props.align_horizontal,



            align_y=props.align_vertical,



            auto_rotate=props.auto_rotate,



        )







        bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)



        if context.area:



            context.area.tag_redraw()







        num_islands = len(islands)



        self.report({'INFO'}, f"Placed {num_islands} UV island(s) edge-to-edge into '{active_box.name}'.")



        return {'FINISHED'}











class UV_OT_target_box_add(bpy.types.Operator):



    """Add a new target bounding box preset"""



    bl_idname = "uv.target_box_add"



    bl_label = "Add Target Box"



    bl_options = {'REGISTER', 'UNDO'}







    def execute(self, context):



        props = context.scene.uv_target_box



        new_box = props.boxes.add()



        count = len(props.boxes)



        new_box.name = f"Target Box {count}"



        new_box.p1 = (0.0, 0.0)



        new_box.p2 = (1.0, 1.0)



        props.active_box_index = count - 1



        props.show_overlay = True



        if context.area:



            context.area.tag_redraw()



        return {'FINISHED'}











class UV_OT_target_box_remove(bpy.types.Operator):



    """Remove the active target bounding box preset"""



    bl_idname = "uv.target_box_remove"



    bl_label = "Remove Target Box"



    bl_options = {'REGISTER', 'UNDO'}







    @classmethod



    def poll(cls, context):



        props = getattr(context.scene, "uv_target_box", None)



        return props and len(props.boxes) > 1







    def execute(self, context):



        props = context.scene.uv_target_box



        idx = props.active_box_index



        props.boxes.remove(idx)



        props.active_box_index = max(0, idx - 1)



        if context.area:



            context.area.tag_redraw()



        return {'FINISHED'}







class UV_OT_target_box_duplicate(bpy.types.Operator):



    """Duplicate the current active target bounding box preset with its parameters"""



    bl_idname = "uv.target_box_duplicate"



    bl_label = "Duplicate Target Box"



    bl_description = "Duplicate the active target box preset and its parameters to a new layer"



    bl_options = {'REGISTER', 'UNDO'}







    @classmethod



    def poll(cls, context):



        props = getattr(context.scene, "uv_target_box", None)



        return props and len(props.boxes) > 0 and props.get_active_box() is not None







    def execute(self, context):



        props = context.scene.uv_target_box



        active_box = props.get_active_box()



        if not active_box:



            self.report({'WARNING'}, "No active target box to duplicate.")



            return {'CANCELLED'}







        count = len(props.boxes) + 1



        existing_names = {b.name for b in props.boxes}







        if active_box.name.startswith("Target Box "):



            candidate = f"Target Box {count}"



            c = count



            while candidate in existing_names:



                c += 1



                candidate = f"Target Box {c}"



            new_name = candidate



        else:



            candidate = f"{active_box.name} (Copy)"



            suffix = 1



            while candidate in existing_names:



                candidate = f"{active_box.name} (Copy {suffix})"



                suffix += 1



            new_name = candidate







        p1_copy = (active_box.p1[0], active_box.p1[1])



        p2_copy = (active_box.p2[0], active_box.p2[1])







        new_box = props.boxes.add()



        new_box.name = new_name



        new_box.p1 = p1_copy



        new_box.p2 = p2_copy







        props.active_box_index = len(props.boxes) - 1



        props.show_overlay = True







        if context.area:



            context.area.tag_redraw()







        self.report({'INFO'}, f"Duplicated '{active_box.name}' as '{new_name}'.")



        return {'FINISHED'}















class UV_OT_target_box_from_selection(bpy.types.Operator):



    """Set active target box coordinates to match the current UV selection bounds"""



    bl_idname = "uv.target_box_from_selection"



    bl_label = "Set Box to Selection"



    bl_options = {'REGISTER', 'UNDO'}







    @classmethod



    def poll(cls, context):



        obj = context.active_object



        return obj and obj.type == 'MESH' and obj.mode == 'EDIT'







    def execute(self, context):



        obj, bm, uv_layer = get_active_mesh_and_bmesh(context)



        if not obj or not bm or not uv_layer:



            self.report({'ERROR'}, "Must be in Mesh Edit mode.")



            return {'CANCELLED'}







        selected_loops = get_selected_uv_elements(context, bm, uv_layer)



        if not selected_loops:



            self.report({'WARNING'}, "No UV elements selected to calculate bounding box.")



            return {'CANCELLED'}







        min_u, min_v, max_u, max_v = get_loops_bounds(selected_loops, uv_layer)



        props = context.scene.uv_target_box



        active_box = props.get_active_box()



        active_box.p1 = (min_u, min_v)



        active_box.p2 = (max_u, max_v)



        props.show_overlay = True







        if context.area:



            context.area.tag_redraw()







        self.report({'INFO'}, f"'{active_box.name}' set to selection: [{min_u:.3f}, {min_v:.3f}] - [{max_u:.3f}, {max_v:.3f}]")



        return {'FINISHED'}











class UV_OT_target_box_reset(bpy.types.Operator):



    """Reset active target box to default [0, 0] - [1, 1] tile coordinates"""



    bl_idname = "uv.target_box_reset"



    bl_label = "Set Box to (0-1) Tile"



    bl_options = {'REGISTER', 'UNDO'}







    def execute(self, context):



        props = context.scene.uv_target_box



        active_box = props.get_active_box()



        active_box.p1 = (0.0, 0.0)



        active_box.p2 = (1.0, 1.0)



        props.show_overlay = True



        if context.area:



            context.area.tag_redraw()



        self.report({'INFO'}, f"'{active_box.name}' reset to (0.0, 0.0) - (1.0, 1.0).")



        return {'FINISHED'}











class UV_OT_target_box_shift(bpy.types.Operator):



    """Shift the active target box by its own dimensions in a cardinal direction (edge-to-edge)"""



    bl_idname = "uv.target_box_shift"



    bl_label = "Shift Box Position"



    bl_options = {'REGISTER', 'UNDO'}







    direction: bpy.props.EnumProperty(



        name="Direction",



        items=[



            ('LEFT', "Left (-Width)", "Shift box left by its width"),



            ('RIGHT', "Right (+Width)", "Shift box right by its width"),



            ('UP', "Up (+Height)", "Shift box up by its height"),



            ('DOWN', "Down (-Height)", "Shift box down by its height"),



        ],



    )







    def execute(self, context):



        props = context.scene.uv_target_box



        active_box = props.get_active_box()







        box_width = abs(active_box.p2[0] - active_box.p1[0])



        box_height = abs(active_box.p2[1] - active_box.p1[1])







        # Guard against zero-sized boxes



        if box_width <= 1e-6:



            box_width = 1.0



        if box_height <= 1e-6:



            box_height = 1.0







        delta_u, delta_v = 0.0, 0.0







        if self.direction == 'LEFT':



            delta_u = -box_width



        elif self.direction == 'RIGHT':



            delta_u = box_width



        elif self.direction == 'UP':



            delta_v = box_height



        elif self.direction == 'DOWN':



            delta_v = -box_height







        active_box.p1[0] += delta_u



        active_box.p1[1] += delta_v



        active_box.p2[0] += delta_u



        active_box.p2[1] += delta_v







        # Optional: shift selected UVs together with box



        if props.move_selection_with_tile:



            obj, bm, uv_layer = get_active_mesh_and_bmesh(context)



            if obj and bm and uv_layer:



                selected_loops = get_selected_uv_elements(context, bm, uv_layer)



                islands = get_uv_islands(bm, uv_layer, selected_loops, expand_to_island=True)



                for island in islands:



                    for loop in island:



                        loop[uv_layer].uv.x += delta_u



                        loop[uv_layer].uv.y += delta_v



                bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)







        if context.area:



            context.area.tag_redraw()







        return {'FINISHED'}











class UV_OT_target_box_set_highlight(bpy.types.Operator):



    """Toggle or set edge highlight for the active target box in the UV viewport"""



    bl_idname = "uv.target_box_set_highlight"



    bl_label = "Set Highlight Edge"



    bl_options = {'INTERNAL'}







    edge: bpy.props.EnumProperty(



        items=[



            ('NONE', "Off", "Turn off edge highlight"),



            ('LEFT', "Left", "Highlight Left (P1 U) edge"),



            ('BOTTOM', "Bottom", "Highlight Bottom (P1 V) edge"),



            ('RIGHT', "Right", "Highlight Right (P2 U) edge"),



            ('TOP', "Top", "Highlight Top (P2 V) edge"),



            ('ALL', "All", "Highlight all 4 edges"),



        ],



        default='NONE',



    )







    def execute(self, context):



        props = context.scene.uv_target_box



        if props.highlight_edge == self.edge:



            props.highlight_edge = 'NONE'



        else:



            props.highlight_edge = self.edge



        if context.area:



            context.area.tag_redraw()



        return {'FINISHED'}











class UV_OT_target_box_draw(bpy.types.Operator):



    """Interactively draw or edit the active custom target box directly in the UV Editor"""



    bl_idname = "uv.target_box_draw"



    bl_label = "Draw / Edit Target Box"



    bl_options = {'REGISTER', 'UNDO'}







    @classmethod



    def poll(cls, context):



        space = context.space_data



        return space and space.type == 'IMAGE_EDITOR'







    def modal(self, context, event):



        props = context.scene.uv_target_box



        active_box = props.get_active_box()



        region = context.region







        # Mouse coordinate to UV space



        u, v = region.view2d.region_to_view(event.mouse_region_x, event.mouse_region_y)







        # Snap to 0.05 increments if Shift is held



        if event.shift:



            u = round(u * 20.0) / 20.0



            v = round(v * 20.0) / 20.0







        min_u = min(active_box.p1[0], active_box.p2[0])



        max_u = max(active_box.p1[0], active_box.p2[0])



        min_v = min(active_box.p1[1], active_box.p2[1])



        max_v = max(active_box.p1[1], active_box.p2[1])







        v2r = region.view2d.view_to_region



        p0 = v2r(min_u, min_v, clip=False)



        p2 = v2r(max_u, max_v, clip=False)



        rx_min = min(p0[0], p2[0])



        rx_max = max(p0[0], p2[0])



        ry_min = min(p0[1], p2[1])



        ry_max = max(p0[1], p2[1])







        mx = event.mouse_region_x



        my = event.mouse_region_y







        if event.type == 'MOUSEMOVE':



            if self.mode == 'DRAW':



                active_box.p2 = (u, v)



                context.area.tag_redraw()



            elif self.mode == 'MOVE':



                du = u - self.last_u



                dv = v - self.last_v



                active_box.p1[0] += du



                active_box.p1[1] += dv



                active_box.p2[0] += du



                active_box.p2[1] += dv



                self.last_u = u



                self.last_v = v



                context.area.tag_redraw()



            elif self.mode == 'DRAG_LEFT':



                active_box.p1[0] = u



                context.area.tag_redraw()



            elif self.mode == 'DRAG_RIGHT':



                active_box.p2[0] = u



                context.area.tag_redraw()



            elif self.mode == 'DRAG_BOTTOM':



                active_box.p1[1] = v



                context.area.tag_redraw()



            elif self.mode == 'DRAG_TOP':



                active_box.p2[1] = v



                context.area.tag_redraw()



            elif self.mode == 'IDLE':



                # Hover detection over edges (within 10 px)



                tol = 10.0



                hovered = 'NONE'



                if abs(mx - rx_min) <= tol and (ry_min - tol <= my <= ry_max + tol):



                    hovered = 'LEFT'



                elif abs(mx - rx_max) <= tol and (ry_min - tol <= my <= ry_max + tol):



                    hovered = 'RIGHT'



                elif abs(my - ry_min) <= tol and (rx_min - tol <= mx <= rx_max + tol):



                    hovered = 'BOTTOM'



                elif abs(my - ry_max) <= tol and (rx_min - tol <= mx <= rx_max + tol):



                    hovered = 'TOP'







                self.hovered_edge = hovered



                if hovered != 'NONE':



                    props.highlight_edge = hovered



                    edge_name = {"LEFT": "Left (P1 U)", "RIGHT": "Right (P2 U)", "BOTTOM": "Bottom (P1 V)", "TOP": "Top (P2 V)"}.get(hovered, "")



                    context.workspace.status_text_set(



                        f"[HOVER: {edge_name}] LMB Drag: Adjust {edge_name} | Shift: Snap 0.05 | Esc: Finish"



                    )



                else:



                    context.workspace.status_text_set(



                        f"[EDIT: {active_box.name}] Hover edge to adjust | LMB inside: Move Box | LMB outside: Draw New | Esc: Confirm"



                    )



                context.area.tag_redraw()







        elif event.type == 'LEFTMOUSE':



            if event.value == 'PRESS':



                if self.hovered_edge == 'LEFT':



                    self.mode = 'DRAG_LEFT'



                elif self.hovered_edge == 'RIGHT':



                    self.mode = 'DRAG_RIGHT'



                elif self.hovered_edge == 'BOTTOM':



                    self.mode = 'DRAG_BOTTOM'



                elif self.hovered_edge == 'TOP':



                    self.mode = 'DRAG_TOP'



                elif (min_u <= u <= max_u) and (min_v <= v <= max_v) and not event.ctrl:



                    self.mode = 'MOVE'



                    self.last_u = u



                    self.last_v = v



                else:



                    self.mode = 'DRAW'



                    active_box.p1 = (u, v)



                    active_box.p2 = (u, v)



                props.show_overlay = True



                context.area.tag_redraw()







            elif event.value == 'RELEASE':



                if self.mode in ('DRAW', 'MOVE', 'DRAG_LEFT', 'DRAG_RIGHT', 'DRAG_BOTTOM', 'DRAG_TOP'):



                    p1_u = min(active_box.p1[0], active_box.p2[0])



                    p2_u = max(active_box.p1[0], active_box.p2[0])



                    p1_v = min(active_box.p1[1], active_box.p2[1])



                    p2_v = max(active_box.p1[1], active_box.p2[1])



                    active_box.p1 = (p1_u, p1_v)



                    active_box.p2 = (p2_u, p2_v)



                    self.mode = 'IDLE'



                    context.area.tag_redraw()







        elif event.type in {'RET', 'NUMPAD_ENTER', 'SPACE'}:



            context.window.cursor_modal_restore()



            context.workspace.status_text_set(None)



            self.report({'INFO'}, f"'{active_box.name}' confirmed.")



            return {'FINISHED'}







        elif event.type in {'ESC', 'RIGHTMOUSE'}:



            active_box.p1 = self.orig_p1



            active_box.p2 = self.orig_p2



            context.area.tag_redraw()



            context.window.cursor_modal_restore()



            context.workspace.status_text_set(None)



            self.report({'INFO'}, "Box editing cancelled.")



            return {'CANCELLED'}







        return {'RUNNING_MODAL'}







    def invoke(self, context, event):



        if context.space_data.type != 'IMAGE_EDITOR':



            self.report({'WARNING'}, "Operator must be run in the UV/Image Editor.")



            return {'CANCELLED'}







        props = context.scene.uv_target_box



        active_box = props.get_active_box()



        props.show_overlay = True



        self.orig_p1 = (active_box.p1[0], active_box.p1[1])



        self.orig_p2 = (active_box.p2[0], active_box.p2[1])



        self.mode = 'IDLE'



        self.hovered_edge = 'NONE'



        self.last_u = 0.0



        self.last_v = 0.0







        context.window.cursor_modal_set('CROSSHAIR')



        context.workspace.status_text_set(



            f"[EDIT: {active_box.name}] Hover edge to adjust | LMB inside: Move | Shift: Snap 0.05 | Enter/Esc: Finish"



        )



        context.window_manager.modal_handler_add(self)



        return {'RUNNING_MODAL'}







# ==============================================================================



# UI PANEL



# ==============================================================================











class UV_UL_target_boxes(bpy.types.UIList):



    """UIList displaying target box presets."""



    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):



        if not item:



            return







        box_label = item.name if (item and item.name and item.name.strip()) else f"Target Box {index + 1}"







        if self.layout_type in {'DEFAULT', 'COMPACT'}:



            row = layout.row(align=True)



            row.prop(item, "name", text="", placeholder=box_label, icon='SHADING_BBOX', emboss=False)



            u_min = min(item.p1[0], item.p2[0])



            u_max = max(item.p1[0], item.p2[0])



            v_min = min(item.p1[1], item.p2[1])



            v_max = max(item.p1[1], item.p2[1])



            row.label(text=f"({u_max-u_min:.2f} x {v_max-v_min:.2f})")



        elif self.layout_type == 'GRID':



            layout.alignment = 'CENTER'



            layout.label(text=box_label, icon='SHADING_BBOX')











class IMAGE_PT_uv_target_box(bpy.types.Panel):



    """Custom Target Box Panel in UV Editor Sidebar"""



    bl_label = "UV Island Target Box"



    bl_idname = "IMAGE_PT_uv_target_box"



    bl_space_type = 'IMAGE_EDITOR'



    bl_region_type = 'UI'



    bl_category = "Target Box"







    @classmethod



    def poll(cls, context):



        return context.space_data and context.space_data.type == 'IMAGE_EDITOR'







    def draw(self, context):



        layout = self.layout



        props = context.scene.uv_target_box



        active_box = props.get_active_box()







        if not active_box:



            col = layout.column(align=True)



            col.scale_y = 1.4



            col.label(text="No target boxes found in scene:")



            col.operator("uv.target_box_add", text="Initialize Target Box 1", icon='ADD')



            return







        # 1. Main Action Button



        col = layout.column(align=True)



        col.scale_y = 1.5



        col.operator("uv.target_box_fit", text=f"Fit Island to '{active_box.name}'", icon='FULLSCREEN_ENTER')







        # 2. Presets Manager (UIList)



        preset_box = layout.box()



        preset_header = preset_box.row(align=True)



        preset_header.label(text="Target Box Presets", icon='PRESET')



        overlay_icon = 'HIDE_OFF' if props.show_overlay else 'HIDE_ON'



        preset_header.prop(props, "show_overlay", text="", icon=overlay_icon)







        row_list = preset_box.row()



        row_list.template_list(



            "UV_UL_target_boxes", "",



            props, "boxes",



            props, "active_box_index",



            rows=3



        )



        col_btns = row_list.column(align=True)



        col_btns.operator("uv.target_box_add", text="", icon='ADD')



        col_btns.operator("uv.target_box_remove", text="", icon='REMOVE')



        col_btns.operator("uv.target_box_duplicate", text="", icon='DUPLICATE')







        row_opts = preset_box.row(align=True)



        row_opts.prop(props, "show_all_boxes", text="Show All Boxes")







        # 3. Active Box Coordinates & Controls



        box = layout.box()



        box_header = box.row(align=True)



        box_header.label(text=f"Active: {active_box.name}", icon='LAYER_ACTIVE')







        draw_row = box.row(align=True)



        draw_row.scale_y = 1.25



        draw_row.operator("uv.target_box_draw", text="Interactive Draw / Edit", icon='GREASEPENCIL')







        # Coordinates and Boundaries



        coord_box = box.box()



        ch_row = coord_box.row(align=True)



        ch_row.label(text="Box Boundary Edges:")



        ch_row.prop(props, "show_edge_labels", text="Labels", toggle=True)







        # Highlight line toggle (Off / On)



        hl_row = coord_box.row(align=True)



        hl_row.label(text="Highlight in Viewport:")



        is_highlight_active = (props.highlight_edge != 'NONE')



        op_off = hl_row.operator("uv.target_box_set_highlight", text="Off", depress=not is_highlight_active)



        op_off.edge = 'NONE'



        op_on = hl_row.operator("uv.target_box_set_highlight", text="On", depress=is_highlight_active)



        op_on.edge = 'ALL'







        col_coords = coord_box.column(align=True)







        # P1 (Min Corner: Left & Bottom)



        p1_box = col_coords.box()



        p1_head = p1_box.row(align=True)



        p1_head.label(text="P1 (Min Corner) — [Bottom-Left]", icon='TRIA_DOWN')







        # Left Edge Card (Cyan)



        b_left = p1_box.box()



        r_left = b_left.row(align=True)



        r_left.label(text="", icon='COLLECTION_COLOR_05')



        r_left.prop(active_box, "p1", index=0, text="Left Edge (P1 U)")



        sw_l = r_left.row(align=True)



        sw_l.scale_x = 0.35



        sw_l.prop(props, "color_left", text="")



        op_l = r_left.operator("uv.target_box_set_highlight", text="", icon='CHECKBOX_HLT' if props.highlight_edge == 'LEFT' else 'CHECKBOX_DEHLT')



        op_l.edge = 'LEFT'







        # Bottom Edge Card (Green)



        b_bot = p1_box.box()



        r_bot = b_bot.row(align=True)



        r_bot.label(text="", icon='COLLECTION_COLOR_04')



        r_bot.prop(active_box, "p1", index=1, text="Bottom Edge (P1 V)")



        sw_b = r_bot.row(align=True)



        sw_b.scale_x = 0.35



        sw_b.prop(props, "color_bottom", text="")



        op_b = r_bot.operator("uv.target_box_set_highlight", text="", icon='CHECKBOX_HLT' if props.highlight_edge == 'BOTTOM' else 'CHECKBOX_DEHLT')



        op_b.edge = 'BOTTOM'







        # P2 (Max Corner: Right & Top)



        p2_box = col_coords.box()



        p2_head = p2_box.row(align=True)



        p2_head.label(text="P2 (Max Corner) — [Top-Right]", icon='TRIA_UP')







        # Right Edge Card (Orange)



        b_right = p2_box.box()



        r_right = b_right.row(align=True)



        r_right.label(text="", icon='COLLECTION_COLOR_02')



        r_right.prop(active_box, "p2", index=0, text="Right Edge (P2 U)")



        sw_r = r_right.row(align=True)



        sw_r.scale_x = 0.35



        sw_r.prop(props, "color_right", text="")



        op_r = r_right.operator("uv.target_box_set_highlight", text="", icon='CHECKBOX_HLT' if props.highlight_edge == 'RIGHT' else 'CHECKBOX_DEHLT')



        op_r.edge = 'RIGHT'







        # Top Edge Card (Pink)



        b_top = p2_box.box()



        r_top = b_top.row(align=True)



        r_top.label(text="", icon='COLLECTION_COLOR_07')



        r_top.prop(active_box, "p2", index=1, text="Top Edge (P2 V)")



        sw_t = r_top.row(align=True)



        sw_t.scale_x = 0.35



        sw_t.prop(props, "color_top", text="")



        op_t = r_top.operator("uv.target_box_set_highlight", text="", icon='CHECKBOX_HLT' if props.highlight_edge == 'TOP' else 'CHECKBOX_DEHLT')



        op_t.edge = 'TOP'







        u_min = min(active_box.p1[0], active_box.p2[0])



        u_max = max(active_box.p1[0], active_box.p2[0])



        v_min = min(active_box.p1[1], active_box.p2[1])



        v_max = max(active_box.p1[1], active_box.p2[1])



        coord_box.label(



            text=f"Dimensions: {u_max - u_min:.4f} x {v_max - v_min:.4f}",



            icon='SNAP_FACE',



        )







        preset_row = box.row(align=True)



        preset_row.operator("uv.target_box_from_selection", text="From Selection", icon='RESTRICT_SELECT_OFF')



        preset_row.operator("uv.target_box_reset", text="0-1 Tile", icon='SNAP_GRID')







        # Move Box Adjacent (D-Pad Cross Layout)



        shift_box = box.box()



        shift_box.label(text="Move Box Adjacent (Edge-to-Edge):")







        # Centered D-Pad container



        dpad_outer = shift_box.row()



        dpad_outer.label(text="")  # Left spacer







        dpad_center = dpad_outer.row(align=True)



        dpad_center.scale_x = 0.85



        dpad_center.scale_y = 1.35







        # Left Column (◄)



        c_left = dpad_center.column(align=True)



        c_left.label(text="")



        op_left = c_left.operator("uv.target_box_shift", text="", icon='TRIA_LEFT')



        op_left.direction = 'LEFT'



        c_left.label(text="")







        # Mid Column (▲ on top, ▼ on bottom)



        c_mid = dpad_center.column(align=True)



        op_up = c_mid.operator("uv.target_box_shift", text="", icon='TRIA_UP')



        op_up.direction = 'UP'



        c_mid.label(text="")



        op_down = c_mid.operator("uv.target_box_shift", text="", icon='TRIA_DOWN')



        op_down.direction = 'DOWN'







        # Right Column (►)



        c_right = dpad_center.column(align=True)



        c_right.label(text="")



        op_right = c_right.operator("uv.target_box_shift", text="", icon='TRIA_RIGHT')



        op_right.direction = 'RIGHT'



        c_right.label(text="")







        dpad_outer.label(text="")  # Right spacer







        shift_box.prop(props, "move_selection_with_tile")







        # 4. Fit Strategy & Placement



        fit_box = layout.box()



        fit_box.label(text="Fitting Strategy", icon='MOD_EDGESPLIT')



        fit_box.prop(props, "fit_mode")







        if props.fit_mode == 'UNIFORM':



            align_row = fit_box.row(align=True)



            align_row.prop(props, "align_horizontal")



            align_row.prop(props, "align_vertical")







        fit_box.prop(props, "auto_rotate")







        # 5. Padding Options (Uniform)



        pad_box = layout.box()



        pad_box.label(text="Padding Options", icon='UV_ISLANDSEL')



        pad_box.prop(props, "padding_mode", expand=True)







        if props.padding_mode == 'UV':



            pad_box.prop(props, "padding_uv", text="Padding (UV)")



            if props.padding_uv == 0.0:



                pad_box.label(text="Strict Edge-to-Edge (0 Padding)", icon='CHECKMARK')



        else:



            pad_box.prop(props, "padding_pixel", text="Padding (px)")



            pad_box.prop(props, "texture_resolution")



            if props.padding_pixel == 0:



                pad_box.label(text="Strict Edge-to-Edge (0 Padding)", icon='CHECKMARK')







# ==============================================================================



# REGISTRATION



# ==============================================================================







classes = (



    UVTargetBoxItem,



    UVTargetBoxProperties,



    UV_OT_target_box_fit,



    UV_OT_target_box_add,



    UV_OT_target_box_remove,



    UV_OT_target_box_duplicate,



    UV_OT_target_box_from_selection,



    UV_OT_target_box_reset,



    UV_OT_target_box_shift,



    UV_OT_target_box_draw,



    UV_OT_target_box_set_highlight,



    UV_UL_target_boxes,



    IMAGE_PT_uv_target_box,



)











def register():



    for cls in classes:



        try:



            bpy.utils.register_class(cls)



        except ValueError:



            bpy.utils.unregister_class(cls)



            bpy.utils.register_class(cls)







    bpy.types.Scene.uv_target_box = bpy.props.PointerProperty(type=UVTargetBoxProperties)







    if on_load_post not in bpy.app.handlers.load_post:



        bpy.app.handlers.load_post.append(on_load_post)







    register_draw_handler()











def unregister():



    unregister_draw_handler()







    if on_load_post in bpy.app.handlers.load_post:



        bpy.app.handlers.load_post.remove(on_load_post)







    if hasattr(bpy.types.Scene, "uv_target_box"):



        del bpy.types.Scene.uv_target_box







    for cls in reversed(classes):



        try:



            bpy.utils.unregister_class(cls)



        except Exception:



            pass











if __name__ == "__main__":



    register()



