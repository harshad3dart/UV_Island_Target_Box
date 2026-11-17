# D:\Antigravity\BlenderGuide\UV_Island_Target_Box_Addon\operators.py
import bpy
import bmesh
from .utils import (
    get_active_mesh_and_bmesh,
    get_selected_uv_elements,
    get_uv_islands,
    get_loops_bounds,
    transform_uv_loops,
)


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
