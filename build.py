"""
Build a standalone SharkPad app with PyInstaller.

Usage (run on the OS you're building for):
    pip install -r requirements.txt
    python build.py

Output lands in dist/:
    Windows: dist/SharkPad.exe
    macOS:   dist/SharkPad.app
    Linux:   dist/SharkPad
"""

import os
import sys

import PyInstaller.__main__

SEP = os.pathsep  # ';' on Windows, ':' on macOS/Linux

DATA_FILES = [
    "OpenDyslexic-Regular.ttf",
    "OpenDyslexic-Bold.ttf",
    "shark_pad_icon.ico",
]

args = [
    "main.py",
    "--name=SharkPad",
    "--windowed",
    "--noconfirm",
    "--clean",
    "--collect-all=faster_whisper",
    # pyspellchecker loads its word lists from data files at import time
    "--collect-data=spellchecker",
]

if sys.platform == "darwin":
    # macOS apps must be a folder bundle (.app); one-file mode is deprecated there
    args += ["--onedir", "--icon=shark_pad_icon.png", "--osx-bundle-identifier=net.sharkpad.app"]
else:
    args.append("--onefile")
    if sys.platform == "win32":
        args.append("--icon=shark_pad_icon.ico")

if sys.platform.startswith("linux"):
    # Qt 6.5+ needs libxcb-cursor to open a window on X11, and many distros
    # don't install it by default, so ship it inside the app
    import glob
    libs = glob.glob("/usr/lib/*/libxcb-cursor.so.0")
    if not libs:
        sys.exit("libxcb-cursor0 is required to build on Linux (sudo apt install libxcb-cursor0)")
    args.append(f"--add-binary={libs[0]}{SEP}.")

for f in DATA_FILES:
    args.append(f"--add-data={f}{SEP}.")

PyInstaller.__main__.run(args)
