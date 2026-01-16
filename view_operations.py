from PySide6.QtWidgets import QPlainTextEdit, QInputDialog

def toggle_word_wrap(editor: QPlainTextEdit):
    """Toggle word wrap on and off."""
    current_mode = editor.lineWrapMode()
    if current_mode == QPlainTextEdit.LineWrapMode.NoWrap:
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        return True
    else:
        editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        return False

def set_font_size(editor: QPlainTextEdit, parent):
    """Ask user for a font size and apply it."""
    current_size = editor.font().pointSize()
    size, ok = QInputDialog.getInt(parent, "Set Font Size", "Font Size:", current_size, 1, 100)
    if ok:
        font = editor.font()
        font.setPointSize(size)
        editor.setFont(font)
        return size
    return current_size
