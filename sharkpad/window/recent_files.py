import os

from PySide6.QtWidgets import QMenu

MAX_RECENT = 8


class RecentFiles:
    def __init__(self, win, open_note):
        self.settings = win.settings
        self.open_note = open_note
        self.menu = QMenu("Open Recent", win)
        self.rebuild()

    def paths(self):
        value = self.settings.value("recent_files", [])
        if isinstance(value, str):
            value = [value]
        return [p for p in (value or []) if isinstance(p, str)]

    def rebuild(self):
        self.menu.clear()
        files = [p for p in self.paths() if os.path.exists(p)]
        if not files:
            empty = self.menu.addAction("No recent notes")
            empty.setEnabled(False)
            return
        for i, path in enumerate(files):
            label = f"&{i + 1}  {os.path.basename(path)}" if i < 9 else os.path.basename(path)
            a = self.menu.addAction(label)
            a.setToolTip(path)
            a.triggered.connect(lambda _=False, p=path: self.open_note(p))
        self.menu.addSeparator()
        self.menu.addAction("Clear List", self.clear)

    def clear(self):
        self.settings.setValue("recent_files", [])
        self.rebuild()

    def add(self, path):
        files = [path] + [p for p in self.paths() if os.path.normcase(p) != os.path.normcase(path)]
        self.settings.setValue("recent_files", files[:MAX_RECENT])
        self.rebuild()

    def remove(self, path):
        self.settings.setValue("recent_files", [p for p in self.paths() if p != path])
        self.rebuild()
