# D:\Antigravity\BlenderGuide\UV_Island_Target_Box_Addon\ui.py
import bpy


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
