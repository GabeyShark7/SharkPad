import re

from PySide6.QtGui import QPalette, QColor, QAction
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QPushButton, QStyleFactory, QWidget

import drawing_operations

# Window/UI colors per theme. The editor gets its own colors on top of these.
THEMES = {
    "Light": {
        "window": "#f0f0f0", "base": "#ffffff", "alt_base": "#f7f7f7",
        "text": "#000000", "button": "#f0f0f0", "highlight": "#d32f2f", "link": "#c62828",
        "disabled": "#8a8a8a", "editor_bg": "#ffffff", "editor_fg": "#000000",
        "dark": False,
    },
    "Dark": {
        "window": "#2b2b2b", "base": "#1e1e1e", "alt_base": "#323232",
        "text": "#f0f0f0", "button": "#3a3a3a", "highlight": "#d32f2f", "link": "#ff6b6b",
        "disabled": "#7a7a7a", "editor_bg": "#1e1e1e", "editor_fg": "#f8f8f2",
        "dark": True,
    },
    "Solarized": {
        "window": "#eee8d5", "base": "#fdf6e3", "alt_base": "#f5efdc",
        "text": "#586e75", "button": "#eee8d5", "highlight": "#dc322f", "link": "#dc322f",
        "disabled": "#93a1a1", "editor_bg": "#fdf6e3", "editor_fg": "#657b83",
        "dark": False,
    },
}


def _build_palette(t):
    p = QPalette()
    window, base, text = QColor(t["window"]), QColor(t["base"]), QColor(t["text"])
    p.setColor(QPalette.Window, window)
    p.setColor(QPalette.WindowText, text)
    p.setColor(QPalette.Base, base)
    p.setColor(QPalette.AlternateBase, QColor(t["alt_base"]))
    p.setColor(QPalette.Text, text)
    p.setColor(QPalette.Button, QColor(t["button"]))
    p.setColor(QPalette.ButtonText, text)
    p.setColor(QPalette.ToolTipBase, base)
    p.setColor(QPalette.ToolTipText, text)
    p.setColor(QPalette.PlaceholderText, QColor(t["disabled"]))
    p.setColor(QPalette.Highlight, QColor(t["highlight"]))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.Link, QColor(t["link"]))
    p.setColor(QPalette.BrightText, QColor("#ff5555"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(t["disabled"]))
    return p


def apply_theme(editor: QPlainTextEdit, theme: str):
    """
    Apply a theme/color scheme to the whole app: window, menus, dialogs,
    drawing pad, and the editor.
    Themes supported: "Light", "Dark", "Solarized"
    """
    t = THEMES.get(theme, THEMES["Light"])

    app = QApplication.instance()
    if app is not None:
        # The native Windows style ignores custom palettes, so use Fusion,
        # which looks the same on Windows, macOS, and Linux.
        app.setStyle(QStyleFactory.create("Fusion"))
        app.setPalette(_build_palette(t))

    editor.setStyleSheet(f"background-color: {t['editor_bg']}; color: {t['editor_fg']};")

    window = editor.window()
    if window is not None:
        # Widgets with their own stylesheet cache the old palette, so
        # re-apply their stylesheet to pick up the new colors.
        for w in [window] + window.findChildren(QWidget):
            sheet = w.styleSheet()
            if sheet:
                w.setStyleSheet("")
                w.setStyleSheet(sheet)

        # Match the drawing canvas to the theme
        for canvas in window.findChildren(drawing_operations.DrawingCanvas):
            canvas.set_dark(t["dark"])


# Matches a trailing shortcut hint like " (Ctrl+O)" or "\n(Ctrl+Shift+D)"
_HINT_RE = re.compile(r"\s*\((?:Ctrl|Shift|Alt)\+[^()]*\)\s*$")


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
