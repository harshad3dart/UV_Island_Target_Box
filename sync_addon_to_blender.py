"""Automated sync script to update and live-reload UV Island Target Box in Blender."""
import os
import sys
import shutil
import socket
import json
import zipfile

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_NAME = "uv_island_target_box"
BLENDER_ADDONS_DIR = os.path.expandvars(
    r"%APPDATA%\Blender Foundation\Blender\5.1\scripts\addons"
)
TARGET_DIR = os.path.join(BLENDER_ADDONS_DIR, ADDON_NAME)

FILES_TO_COPY = [
    "__init__.py",
    "properties.py",
    "operators.py",
    "draw.py",
    "ui.py",
    "utils.py",
]


def sync_files():
    """Copy latest addon files to Blender addons directory."""
    os.makedirs(TARGET_DIR, exist_ok=True)
    for fname in FILES_TO_COPY:
        src = os.path.join(SOURCE_DIR, fname)
        dst = os.path.join(TARGET_DIR, fname)
        if os.path.exists(src):
            shutil.copy2(src, dst)
    print(f"[Sync] Copied {len(FILES_TO_COPY)} files to {TARGET_DIR}")


def build_zip():
    """Build UV_Island_Target_Box.zip."""
    zip_path = os.path.join(SOURCE_DIR, "UV_Island_Target_Box.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in FILES_TO_COPY:
            fpath = os.path.join(SOURCE_DIR, fname)
            if os.path.exists(fpath):
                zf.write(fpath, arcname=f"{ADDON_NAME}/{fname}")
    print(f"[Build] Built {zip_path}")


def reload_in_blender(host="127.0.0.1", port=9876):
    """Send live-reload command to Blender via its MCP socket."""
    code = f"""
import bpy, addon_utils, sys

addon_name = '{ADDON_NAME}'
try:
    addon_utils.disable(addon_name, default_set=True)
except Exception:
    pass

for m in list(sys.modules.keys()):
    if m == addon_name or m.startswith(addon_name + '.'):
        del sys.modules[m]

addon_utils.enable(addon_name, default_set=True)

for window in bpy.context.window_manager.windows:
    for area in window.screen.areas:
        area.tag_redraw()

scene = bpy.context.scene
props = getattr(scene, 'uv_target_box', None)
result = {{
    'reloaded': True,
    'addon': addon_name,
    'boxes': len(props.boxes) if props else 0
}}
"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5.0)
        s.connect((host, port))
        payload = json.dumps({"type": "execute", "code": code, "strict_json": False}) + "\x00"
        s.sendall(payload.encode("utf-8"))

        res = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            res += chunk
            if b"\x00" in res:
                break
        s.close()
        response = json.loads(res.decode("utf-8").rstrip("\x00"))
        print(f"[MCP Live Reload] Success: {response}")
        return True
    except ConnectionRefusedError:
        print("[MCP Live Reload] Blender socket is not running (Blender closed or MCP disabled).")
        return False
    except Exception as e:
        print(f"[MCP Live Reload] Error: {e}")
        return False


if __name__ == "__main__":
    sync_files()
    build_zip()
    reload_in_blender()
