import re

from PySide6.QtGui import QPalette, QColor, QAction
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QPushButton, QStyleFactory, QWidget

import drawing_operations

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
    "Cream": {
        "window": "#efe6d2", "base": "#fbf3e0", "alt_base": "#f4ead4",
        "text": "#2b2b2b", "button": "#efe6d2", "highlight": "#b23a2a", "link": "#b23a2a",
        "disabled": "#8c8273", "editor_bg": "#fbf3e0", "editor_fg": "#1f1f1f",
        "dark": False,
    },
    "High Contrast": {
        "window": "#000000", "base": "#000000", "alt_base": "#1a1a1a",
        "text": "#ffffff", "button": "#000000", "highlight": "#ffff00", "link": "#00ffff",
        "disabled": "#bfbfbf", "editor_bg": "#000000", "editor_fg": "#ffffff",
        "dark": True, "highlighted_text": "#000000",
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
    p.setColor(QPalette.HighlightedText, QColor(t.get("highlighted_text", "#ffffff")))
    p.setColor(QPalette.Link, QColor(t["link"]))
    p.setColor(QPalette.BrightText, QColor("#ff5555"))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(t["disabled"]))
    return p


def _rgba(hex_color, alpha):
    c = QColor(hex_color)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


def scrollbar_style(t):
    high_contrast = bool(t.get("highlighted_text"))
    ink = "#ffff00" if high_contrast else t["text"]
    idle, hover, pressed = (_rgba(ink, a) for a in ((0.55, 0.8, 1.0) if high_contrast else (0.28, 0.45, 0.6)))
    boxes = """
QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid #ffffff; background: #000000; }
QCheckBox::indicator:checked { background: #ffff00; border: 1px solid #ffff00; }
""" if high_contrast else ""
    return boxes + f"""
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {idle}; min-height: 32px; margin: 3px 3px 3px 3px; border-radius: 3px; }}
QScrollBar::handle:horizontal {{ background: {idle}; min-width: 32px; margin: 3px 3px 3px 3px; border-radius: 3px; }}
QScrollBar::handle:hover {{ background: {hover}; }}
QScrollBar::handle:pressed {{ background: {pressed}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; border: none; background: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QAbstractScrollArea::corner {{ background: transparent; }}
"""


def apply_theme(editor: QPlainTextEdit, theme: str):
    """
    Apply a theme/color scheme to the whole app: window, menus, dialogs,
    drawing pad, and the editor.
    Themes supported: "Light", "Dark", "Solarized"
    """
    t = THEMES.get(theme, THEMES["Light"])

    app = QApplication.instance()
    if app is not None:
        app.setStyle(QStyleFactory.create("Fusion"))
        app.setPalette(_build_palette(t))
        app.setStyleSheet(scrollbar_style(t))

    editor.setStyleSheet(
        f"QPlainTextEdit {{ background-color: {t['editor_bg']}; color: {t['editor_fg']}; border: none; }}")

    window = editor.window()
    if window is not None:
        for w in [window] + window.findChildren(QWidget):
            sheet = w.styleSheet()
            if sheet:
                w.setStyleSheet("")
                w.setStyleSheet(sheet)

        for canvas in window.findChildren(drawing_operations.DrawingCanvas):
            canvas.set_dark(t["dark"])


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
