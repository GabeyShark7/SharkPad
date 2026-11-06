"""
Build a standalone SharkPad executable with PyInstaller.

Usage (run on the OS you're building for):
    pip install -r requirements.txt
    python build.py

Output lands in dist/.
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
    "--onefile",
    "--windowed",
    "--noconfirm",
    "--clean",
    "--collect-all=faster_whisper",
]

if sys.platform == "win32":
    args.append("--icon=shark_pad_icon.ico")
elif sys.platform == "darwin":
    args.append("--icon=shark_pad_icon.png")

for f in DATA_FILES:
    args.append(f"--add-data={f}{SEP}.")

PyInstaller.__main__.run(args)
