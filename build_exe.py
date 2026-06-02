#!/usr/bin/env python3
"""
Build a standalone Windows .exe of Doc Unlocker with PyInstaller.

Usage:
    py -m pip install --user pyinstaller
    py build_exe.py

Result:  dist/DocUnlocker.exe   (git-ignored; ship as a Release asset)

Size: the build excludes large libraries that aren't used and enables UPX
compression when a `upx` executable is available (on PATH, or in tools/upx/).
"""
import os
import sys
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

# Heavy libraries that may be present in the environment but are NOT used by
# the app at runtime - excluding them keeps the binary small.
EXCLUDES = [
    "numpy", "scipy", "pandas", "matplotlib", "PIL", "Pillow",
    "pytest", "IPython", "notebook", "tcl8", "setuptools", "pip",
    "wheel", "lib2to3", "pydoc_data",
]


def find_upx_dir():
    """Return a directory containing upx(.exe) if we can find one, else None."""
    on_path = shutil.which("upx")
    if on_path:
        return os.path.dirname(on_path)
    for root, _dirs, files in os.walk(os.path.join(HERE, "tools")):
        if any(f.lower() in ("upx", "upx.exe") for f in files):
            return root
    return None


def main():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed",
        "--name", "DocUnlocker",
        "--noconfirm", "--clean",
    ]
    sep = ";" if os.name == "nt" else ":"
    icon = os.path.join(HERE, "assets", "icon.ico")
    if os.path.isfile(icon):
        cmd += ["--icon", icon]
        cmd += ["--add-data", f"{icon}{sep}assets"]
    icon_png = os.path.join(HERE, "assets", "icon.png")
    if os.path.isfile(icon_png):
        cmd += ["--add-data", f"{icon_png}{sep}assets"]
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    upx_dir = find_upx_dir()
    if upx_dir:
        cmd += ["--upx-dir", upx_dir]
        print("Using UPX from:", upx_dir)
    else:
        print("UPX not found - building without extra compression.")
        print("  (Optional: put upx.exe in tools/upx/ or on PATH to shrink the exe.)")
    cmd.append(os.path.join(HERE, "doc_unlocker.py"))

    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=HERE)
    out = os.path.join(HERE, "dist", "DocUnlocker.exe")
    if os.path.isfile(out):
        print(f"\nDone -> {out}  ({os.path.getsize(out)/1048576:.1f} MB)")


if __name__ == "__main__":
    main()
