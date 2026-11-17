# D:\Antigravity\BlenderGuide\UV_Island_Target_Box_Addon\draw.py
import bpy
import blf
import gpu
import math
from gpu_extras.batch import batch_for_shader

_draw_handler = None


def get_shader():
    """Safely retrieves a 2D uniform color shader."""
    for name in ('UNIFORM_COLOR', '2D_UNIFORM_COLOR'):
        try:
            return gpu.shader.from_builtin(name)
        except Exception:
            continue
    return None


def draw_thick_line_quad(shader, pt_a, pt_b, color, thickness=3.0):
    """Draws a thick line as a quad (two triangles) for consistent rendering across all GPU drivers."""
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
        gpu.state.blend_set('ALPHA')
        batch = batch_for_shader(shader, 'TRIS', {"pos": tris})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
    except Exception:
        pass


def draw_box_rect(shader, p0, p1, p2, p3, fill_color=None, border_color=None, line_width=1.5):
    """Draws a rectangle with optional fill and border."""
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
    if bpy.app.background:
        return
    old_h = bpy.app.driver_namespace.get('uv_target_box_draw_handler') or _draw_handler
    if old_h is not None:
        try:
            bpy.types.SpaceImageEditor.draw_handler_remove(old_h, 'WINDOW')
        except Exception:
            pass
        bpy.app.driver_namespace.pop('uv_target_box_draw_handler', None)
        _draw_handler = None

    _draw_handler = bpy.types.SpaceImageEditor.draw_handler_add(
        draw_target_box_callback, (), 'WINDOW', 'POST_PIXEL'
    )
    bpy.app.driver_namespace['uv_target_box_draw_handler'] = _draw_handler


def unregister_draw_handler():
    global _draw_handler
    h = bpy.app.driver_namespace.pop('uv_target_box_draw_handler', None) or _draw_handler
    if h is not None:
        try:
            bpy.types.SpaceImageEditor.draw_handler_remove(h, 'WINDOW')
        except Exception:
            pass
    _draw_handler = None
