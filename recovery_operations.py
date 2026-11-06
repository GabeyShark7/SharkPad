# Crash recovery for SharkPad: keeps a copy of unsaved notes so they can be
# brought back if the app closes unexpectedly.

import datetime
import json
import os

from PySide6.QtCore import QStandardPaths


def _path():
    folder = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    if not folder:
        folder = os.path.join(os.path.expanduser("~"), ".sharkpad")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "recovery.json")


def save(text, file_path):
    data = {"text": text, "file": file_path, "saved_at": datetime.datetime.now().isoformat(timespec="seconds")}
    path = _path()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)  # never leaves a half-written backup
    except OSError:
        pass


def load():
    """Returns the saved backup dict, or None."""
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if data.get("text", "").strip() else None
    except (OSError, ValueError):
        return None


def clear():
    try:
        os.remove(_path())
    except OSError:
        pass
