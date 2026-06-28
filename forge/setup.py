"""
FORGE Setup — creates a Desktop shortcut and optional Start Menu entry.
Run once after installing:  python setup.py

What it does:
  1. Creates a .lnk shortcut on your Desktop pointing to "Launch FORGE.bat"
  2. Optionally adds it to Start Menu > FORGE
  3. Creates a small FORGE icon (.ico) if one doesn't exist
"""

import os
import sys
import struct
import shutil
from pathlib import Path


def create_shortcut(target: str, shortcut_path: str,
                    working_dir: str, description: str,
                    icon_path: str = None):
    """Create a Windows .lnk shortcut using the Windows Script Host."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        lnk = shell.CreateShortcut(shortcut_path)
        lnk.TargetPath = target
        lnk.WorkingDirectory = working_dir
        lnk.Description = description
        if icon_path and os.path.exists(icon_path):
            lnk.IconLocation = icon_path
        lnk.Save()
        return True, "win32com"
    except ImportError:
        pass  # Try alternative

    # Alternative: use PowerShell to create the shortcut
    ps_cmd = (
        f"$WshShell = New-Object -comObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{shortcut_path}'); "
        f"$Shortcut.TargetPath = '{target}'; "
        f"$Shortcut.WorkingDirectory = '{working_dir}'; "
        f"$Shortcut.Description = '{description}'; "
    )
    if icon_path and os.path.exists(icon_path):
        ps_cmd += f"$Shortcut.IconLocation = '{icon_path}'; "
    ps_cmd += "$Shortcut.Save()"

    ret = os.system(f'powershell -Command "{ps_cmd}"')
    return (ret == 0), "powershell"


def create_ico():
    """Create a minimal FORGE icon (.ico) using Pillow if available."""
    forge_dir = Path(__file__).parent
    ico_path = forge_dir / "forge_icon.ico"
    if ico_path.exists():
        return str(ico_path)

    try:
        from PIL import Image, ImageDraw, ImageFont
        # Create a 64x64 icon with the FORGE anvil look
        img = Image.new("RGBA", (64, 64), (10, 10, 11, 255))
        draw = ImageDraw.Draw(img)
        # Purple circle
        draw.ellipse([4, 4, 60, 60], fill=(139, 92, 246, 255))
        # White "F" text
        try:
            font = ImageFont.truetype("arial.ttf", 36)
        except Exception:
            font = ImageFont.load_default()
        draw.text((18, 10), "F", fill=(255, 255, 255, 255), font=font)
        img.save(str(ico_path), format="ICO",
                 sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
        return str(ico_path)
    except Exception:
        return ""


def main():
    print()
    print("  [FORGE Setup]")
    print("  -------------------------------------------")
    print()

    forge_dir = Path(__file__).parent.resolve()
    bat_file  = forge_dir / "Launch FORGE.bat"

    if not bat_file.exists():
        print(f"[ERROR] Launcher not found: {bat_file}")
        print("        Make sure you run this from the forge/ directory.")
        input("Press Enter to exit...")
        return

    # Create icon
    print("  [1/3] Creating icon...")
    ico_path = create_ico()
    if ico_path:
        print(f"        OK -> {ico_path}")
    else:
        print("        Skipped (Pillow not installed -- icon will be generic)")

    # Desktop shortcut
    print("  [2/3] Creating Desktop shortcut...")
    desktop = Path.home() / "Desktop"
    if not desktop.exists():
        desktop = Path.home() / "OneDrive" / "Desktop"
    shortcut_path = str(desktop / "FORGE.lnk")

    ok, method = create_shortcut(
        target=str(bat_file),
        shortcut_path=shortcut_path,
        working_dir=str(forge_dir),
        description="FORGE -- Multi-Agent AI Development Studio",
        icon_path=ico_path,
    )
    if ok:
        print(f"        OK -> {shortcut_path}  (via {method})")
    else:
        print(f"        [WARN] Could not create shortcut automatically.")
        print(f"        Manually right-click '{bat_file.name}' -> Send to -> Desktop")

    # Start Menu entry
    print("  [3/3] Adding Start Menu entry...")
    start_menu = (
        Path(os.environ.get("APPDATA", "")) /
        "Microsoft" / "Windows" / "Start Menu" / "Programs" / "FORGE"
    )
    try:
        start_menu.mkdir(parents=True, exist_ok=True)
        sm_path = str(start_menu / "FORGE.lnk")
        ok2, _ = create_shortcut(
            target=str(bat_file),
            shortcut_path=sm_path,
            working_dir=str(forge_dir),
            description="FORGE -- Multi-Agent AI Development Studio",
            icon_path=ico_path,
        )
        if ok2:
            print(f"        OK -> {sm_path}")
        else:
            print("        [WARN] Start Menu entry could not be created.")
    except Exception as e:
        print(f"        [WARN] {e}")

    print()
    print("  Setup complete!")
    print()
    print("  You can now double-click the FORGE shortcut on your Desktop,")
    print(f"  or run: \"{bat_file}\"")
    print()
    input("  Press Enter to exit...")



if __name__ == "__main__":
    main()
