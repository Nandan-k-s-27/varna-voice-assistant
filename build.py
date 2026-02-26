"""
VARNA v2.3 — Build Script
Creates a distributable Windows executable using PyInstaller.

Usage:
    python build.py

Output:
    dist/VARNA/          — Folder with all files
    dist/VARNA/VARNA.exe — Main executable

After building:
    1. Test: cd dist/VARNA && VARNA.exe
    2. Create installer: Open installer.iss in Inno Setup → Compile
"""

import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def clean():
    """Remove previous build artifacts."""
    print("🧹 Cleaning previous build...")
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
            print(f"   Removed {d}")


def build():
    """Run PyInstaller with the spec file."""
    print("📦 Building VARNA executable...")
    spec_file = ROOT / "varna.spec"
    if not spec_file.exists():
        print("❌ varna.spec not found!")
        sys.exit(1)

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec_file)],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print("❌ PyInstaller build failed!")
        sys.exit(1)

    print("✅ Build successful!")
    print(f"   Output: {DIST / 'VARNA'}")


def copy_extras():
    """Copy config and data files that PyInstaller might miss."""
    output = DIST / "VARNA"
    if not output.exists():
        return

    extras = ["config.json", "commands.json"]
    for name in extras:
        src = ROOT / name
        dst = output / name
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)
            print(f"   Copied {name}")

    # Copy assets folder
    assets_src = ROOT / "assets"
    assets_dst = output / "assets"
    if assets_src.exists() and not assets_dst.exists():
        shutil.copytree(assets_src, assets_dst)
        print("   Copied assets/")


def main():
    print("=" * 50)
    print("  VARNA v2.3 — Build Script")
    print("=" * 50)
    print()

    clean()
    build()
    copy_extras()

    print()
    print("=" * 50)
    print("  BUILD COMPLETE")
    print("=" * 50)
    print()
    print("Next steps:")
    print("  1. Test: cd dist\\VARNA && VARNA.exe")
    print("  2. Install Inno Setup: https://jrsoftware.org/isinfo.php")
    print("  3. Open installer.iss in Inno Setup → Compile")
    print("  4. Output: installer_output\\VARNA_Setup_v2.3.exe")


if __name__ == "__main__":
    main()
