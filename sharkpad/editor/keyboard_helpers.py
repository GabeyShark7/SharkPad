from PySide6.QtCore import QEvent, QObject, Qt


class LetterUndo(QObject):
    """Make Ctrl+Z undo one letter at a time.

    Qt merges everything typed (or backspaced) since the last Enter into a
    single undo step, so one Ctrl+Z could erase a whole paragraph. Each
    keystroke here becomes its own step.
    """

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        editor.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() != QEvent.KeyPress or obj is not self.editor or self.editor.isReadOnly():
            return False
        if event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier):
            return False

        c = self.editor.textCursor()
        key, text = event.key(), event.text()
        if key == Qt.Key_Backspace:
            action = c.deletePreviousChar
        elif key == Qt.Key_Delete:
            action = c.deleteChar
        elif len(text) == 1 and text.isprintable():
            action = lambda: c.insertText(text)
        else:
            return False

        c.beginEditBlock()
        action()
        c.endEditBlock()
        self.editor.setTextCursor(c)
        self.editor.ensureCursorVisible()
        return True


class CtrlWheelZoom(QObject):
    """Ctrl + mouse wheel calls `callback(+1 or -1)` instead of Qt's own zoom."""

    def __init__(self, callback, parent=None):
        super().__init__(parent)
        self.callback = callback

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and event.modifiers() & Qt.ControlModifier:
            dy = event.angleDelta().y()
            if dy:
                self.callback(1 if dy > 0 else -1)
            return True
        return False
