from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QPlainTextEdit

def apply_theme(editor: QPlainTextEdit, theme: str):
    """
    Apply a theme/color scheme to the editor.
    Themes supported: "Light", "Dark", "Solarized"
    """
    palette = editor.palette()
    
    if theme == "Light":
        editor.setStyleSheet("background-color: white; color: black;")
    elif theme == "Dark":
        editor.setStyleSheet("background-color: #2b2b2b; color: #f8f8f2;")
    elif theme == "Solarized":
        editor.setStyleSheet("background-color: #fdf6e3; color: #657b83;")
    else:
        editor.setStyleSheet("")  # Reset to default
