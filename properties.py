# D:\Antigravity\BlenderGuide\UV_Island_Target_Box_Addon\properties.py
import bpy


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


def register():
    try:
        bpy.utils.register_class(UVTargetBoxItem)
    except ValueError:
        pass

    try:
        bpy.utils.register_class(UVTargetBoxProperties)
    except ValueError:
        pass

    bpy.types.Scene.uv_target_box = bpy.props.PointerProperty(type=UVTargetBoxProperties)

    if on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_load_post)


def unregister():
    if on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_load_post)

    if hasattr(bpy.types.Scene, "uv_target_box"):
        del bpy.types.Scene.uv_target_box

    try:
        bpy.utils.unregister_class(UVTargetBoxProperties)
    except Exception:
        pass

    try:
        bpy.utils.unregister_class(UVTargetBoxItem)
    except Exception:
        pass
