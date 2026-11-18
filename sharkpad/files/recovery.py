import datetime
import json
import os

from sharkpad.paths import app_data_path


def _path():
    return app_data_path("recovery.json")


def save(text, file_path):
    data = {"text": text, "file": file_path, "saved_at": datetime.datetime.now().isoformat(timespec="seconds")}
    path = _path()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
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
