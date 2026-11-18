import re

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QPushButton

_HINT_RE = re.compile(r"\s*\((?:(?:Ctrl|Shift|Alt)\+[^()]*|F\d{1,2}|Esc)\)\s*$")


def set_hinted_text(widget, text, show):
    """Set a button or menu item's text, keeping or hiding its shortcut hint."""
    widget.setProperty("full_text", text)
    widget.setText(text if show else _HINT_RE.sub("", text))


def apply_shortcut_hints(window, show):
    """Show or hide the "(Ctrl+...)" hints on every button and menu item."""
    for w in window.findChildren(QPushButton) + window.findChildren(QAction):
        full = w.property("full_text")
        if not full:
            full = w.text()
            if not _HINT_RE.search(full):
                continue
        set_hinted_text(w, full, show)
