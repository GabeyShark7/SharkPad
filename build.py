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
]

if sys.platform == "darwin":
    # macOS apps must be a folder bundle (.app); one-file mode is deprecated there
    args += ["--onedir", "--icon=shark_pad_icon.png", "--osx-bundle-identifier=net.sharkpad.app"]
else:
    args.append("--onefile")
    if sys.platform == "win32":
        args.append("--icon=shark_pad_icon.ico")

for f in DATA_FILES:
    args.append(f"--add-data={f}{SEP}.")

PyInstaller.__main__.run(args)
