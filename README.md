# UV Island Target Box - Blender Addon

A Blender addon for creating custom target bounding boxes in the UV Editor and fitting UV islands **strictly edge-to-edge** with zero padding (or customizable margin/padding), with support for **multiple target box presets**.

---

## 📁 Files in this Folder

- **`UV_Island_Target_Box.zip`**: Ready-to-install addon zip package.
- **`uv_island_target_box_single.py`**: Self-contained single-file version (can be installed directly as a `.py` addon or run inside Blender's Scripting workspace).
- **`__init__.py`, `operators.py`, `ui.py`, `properties.py`, `draw.py`, `utils.py`**: Modular source code.
- **`test_addon.py`**: Automated verification test suite.

---

## 🚀 Installation

1. Open Blender.
2. Go to **Edit > Preferences > Add-ons**.
3. Click the menu/down arrow in the top right, select **Install from Disk...** (or **Install...**).
4. Select `UV_Island_Target_Box.zip` (or `uv_island_target_box_single.py`).
5. Enable the checkbox for **UV: UV Island Target Box**.

---

## 🎯 How to Use

1. Open the **UV Editor** and press `N` to open the sidebar.
2. Click on the **Target Box** tab.
3. In 3D Viewport or UV Editor, enter **Edit Mode** and select the faces/islands you want to place.
4. Set up your target boxes:
   - Use the **Target Box Presets** list to add (`+`), remove (`-`), or rename boxes (e.g. "Trim Sheet Top", "Decal Zone", "Tile 1001").
   - Click **Interactive Draw / Edit** to click-and-drag the active box directly in the UV Editor.
   - Or enter coordinates manually (**P1** Min U/V, **P2** Max U/V).
   - Or click **From Selection** to snap the box to your current UV selection.
   - Or use the **UDIM Shift arrows** (`<`, `>`, `v`, `^`) to jump to adjacent tiles.
5. Click **Fit Island to '[Box Name]'** to place the island edge-to-edge.

---

## ⚙️ Key Features & Settings

### 1. Target Box Presets & Multi-Box Viewport Overlay
- **Presets List**: Save multiple named target areas. Switch between them with one click.
- **Show All Boxes**: Active box is drawn with bright yellow borders, semi-transparent fill, and corner handles. Inactive boxes are drawn with subtle faint outlines and their name badges so you can see all your zones at a glance.

### 2. Edge-to-Edge Placement (Zero Padding by Default)
- **Zero Padding Default**: Islands touch the target box boundaries edge-to-edge with no unwanted margins.
- **Optional Uniform Padding**:
  - **UV Space**: Specify inner margin in UV units (e.g. `0.02`).
  - **Pixels**: Specify inner margin in pixels (e.g. `2px`, `4px`) based on active image resolution.
  - Visual preview: When padding > 0, an inner light cyan box shows the padded placement boundary in real time.

### 3. Fitting Strategies
- **Stretch to Fill**: Scales the island non-uniformly to touch all 4 edges of the target box.
- **Fit Uniform**: Preserves original aspect ratio, touching the target box along the dominant axis. Includes **Align X** (Left, Center, Right) and **Align Y** (Bottom, Center, Top).
- **Auto Orient**: Automatically rotates islands 90° if their aspect ratio matches the target box better.

### 4. Interactive Viewport Drawing
- **Golden Bounding Box**: Live overlay rendered directly in the UV Editor viewport.
- **Corner Handles**: Visual handles at all four corners with live dimension readouts.
- **Shortcuts during Box Edit**:
  - `LMB Drag`: Draw new box or move existing box.
  - `Shift`: Snap to `0.05` grid increments.
  - `Ctrl`: Force draw a new box from scratch.
  - `Enter` / `Space`: Confirm.
  - `Esc` / `RMB`: Cancel.
