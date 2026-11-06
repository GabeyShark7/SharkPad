# Editing helpers for SharkPad: highlight layers, undo-friendly text replacement,
# find & replace, line tools, and Ctrl+mouse-wheel zoom.

import datetime


from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor, QTextDocument, QTextFormat
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QWidget

# Highlights are drawn on top of the text without changing it, so they never
# end up in the undo history. Later layers draw over earlier ones.
LAYER_ORDER = ["line", "find", "speech", "spell"]


def set_selection_layer(editor, name, selections):
    layers = getattr(editor, "_selection_layers", None)
    if layers is None:
        layers = {}
        editor._selection_layers = layers
    layers[name] = list(selections)
    combined = []
    for key in LAYER_ORDER:
        combined.extend(layers.get(key, []))
    editor.setExtraSelections(combined)


def make_selection(cursor, fmt):
    sel = QTextEdit.ExtraSelection()
    sel.cursor = cursor
    sel.format = fmt
    return sel


def range_cursor(editor, start, end):
    c = QTextCursor(editor.document())
    c.setPosition(start)
    c.setPosition(end, QTextCursor.KeepAnchor)
    return c


def replace_range(editor, start, end, text):
    """Replace part of the text as one step that Ctrl+Z can undo."""
    c = range_cursor(editor, start, end)
    c.beginEditBlock()
    c.insertText(text)
    c.endEditBlock()
    return c


def replace_all_text(editor, text):
    """Replace the whole document as one undoable step (setPlainText would wipe undo history)."""
    return replace_range(editor, 0, editor.document().characterCount() - 1, text)


READING_GUIDE_COLOR = QColor(255, 193, 7, 70)


def update_reading_guide(editor, enabled):
    """Tint the line the cursor is on, like a reading ruler."""
    if not enabled:
        set_selection_layer(editor, "line", [])
        return
    fmt = QTextCharFormat()
    fmt.setBackground(READING_GUIDE_COLOR)
    fmt.setProperty(QTextFormat.FullWidthSelection, True)
    c = editor.textCursor()
    c.clearSelection()
    set_selection_layer(editor, "line", [make_selection(c, fmt)])


def duplicate_line(editor):
    """Copy the current line (or the selection) right below it."""
    c = editor.textCursor()
    c.beginEditBlock()
    if c.hasSelection():
        text = c.selectedText().replace(" ", "\n")
        c.setPosition(c.selectionEnd())
        c.insertText(text)
    else:
        c.movePosition(QTextCursor.StartOfBlock)
        c.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
        text = c.selectedText()
        c.clearSelection()
        c.insertText("\n" + text)
    c.endEditBlock()


def move_lines(editor, up):
    """Move the current line (or every selected line) up or down by one."""
    doc = editor.document()
    c = editor.textCursor()
    first = doc.findBlock(c.selectionStart())
    last = doc.findBlock(c.selectionEnd())
    if c.hasSelection() and last != first and c.selectionEnd() == last.position():
        last = last.previous()

    neighbor = first.previous() if up else last.next()
    if not neighbor.isValid():
        return

    start = first.position()
    end = last.position() + last.length() - 1
    lines = range_cursor(editor, start, end).selectedText().replace(" ", "\n")
    anchor_off, pos_off = c.anchor() - start, c.position() - start

    if up:
        region = (neighbor.position(), end)
        new_text = lines + "\n" + neighbor.text()
        new_start = neighbor.position()
    else:
        region = (start, neighbor.position() + neighbor.length() - 1)
        new_text = neighbor.text() + "\n" + lines
        new_start = start + len(neighbor.text()) + 1

    replace_range(editor, region[0], region[1], new_text)
    c = editor.textCursor()
    c.setPosition(new_start + anchor_off)
    c.setPosition(new_start + pos_off, QTextCursor.KeepAnchor)
    editor.setTextCursor(c)


def insert_date_time(editor):
    now = datetime.datetime.now()
    hour = now.strftime("%I").lstrip("0") or "12"
    editor.insertPlainText(f"{now:%A, %B} {now.day}, {now.year} {hour}:{now:%M %p}")


def text_stats(editor):
    """Word/character counts and cursor position for the status bar."""
    text = editor.toPlainText()
    words = len(text.split())
    c = editor.textCursor()
    line = c.blockNumber() + 1
    col = c.positionInBlock() + 1
    parts = []
    if c.hasSelection():
        sel_words = len(c.selectedText().replace(" ", " ").split())
        parts.append(f"{sel_words} of {words} words selected")
    else:
        parts.append(f"{words} word{'s' if words != 1 else ''}")
        parts.append(f"{len(text)} characters")
        minutes = words / 200
        if words >= 200:
            parts.append(f"about {round(minutes)} min read")
    parts.append(f"Line {line}, Col {col}")
    return "   ·   ".join(parts)


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

        # Doing it inside its own edit block stops Qt merging it into the previous step
        c.beginEditBlock()
        action()
        c.endEditBlock()
        self.editor.setTextCursor(c)
        self.editor.ensureCursorVisible()
        return True


def insert_as_own_step(editor, text):
    """Insert text (e.g. a dictated phrase) as a separate undo step."""
    c = editor.textCursor()
    c.beginEditBlock()
    c.insertText(text)
    c.endEditBlock()
    editor.setTextCursor(c)
    editor.ensureCursorVisible()


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


class FindBar(QWidget):
    """Find & replace bar shown under the editor (Ctrl+F / Ctrl+H)."""

    MAX_HIGHLIGHTS = 2000

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self.setAccessibleName("Find and replace")

        row = QHBoxLayout(self)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(6)

        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find")
        self.find_edit.setAccessibleName("Find text")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.textChanged.connect(self._search_changed)
        self.find_edit.installEventFilter(self)
        row.addWidget(self.find_edit, 2)

        self.prev_btn = QPushButton("Previous")
        self.prev_btn.setToolTip("Previous match (Shift+F3 or Shift+Enter)")
        self.prev_btn.clicked.connect(lambda: self.find_next(backward=True))
        self.next_btn = QPushButton("Next")
        self.next_btn.setToolTip("Next match (F3 or Enter)")
        self.next_btn.clicked.connect(lambda: self.find_next())
        row.addWidget(self.prev_btn)
        row.addWidget(self.next_btn)

        self.case_box = QCheckBox("Match case")
        self.case_box.toggled.connect(self._search_changed)
        row.addWidget(self.case_box)

        self.count_label = QLabel()
        self.count_label.setMinimumWidth(90)
        row.addWidget(self.count_label)

        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace with")
        self.replace_edit.setAccessibleName("Replace with")
        self.replace_edit.returnPressed.connect(self.replace_one)
        row.addWidget(self.replace_edit, 2)
        self.replace_btn = QPushButton("Replace")
        self.replace_btn.clicked.connect(self.replace_one)
        self.replace_all_btn = QPushButton("Replace All")
        self.replace_all_btn.clicked.connect(self.replace_all)
        row.addWidget(self.replace_btn)
        row.addWidget(self.replace_all_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedWidth(30)
        close_btn.setToolTip("Close (Esc)")
        close_btn.setAccessibleName("Close find bar")
        close_btn.clicked.connect(self.close_bar)
        row.addWidget(close_btn)

        editor.textChanged.connect(self._refresh_if_open)
        self.hide()

    def open(self, replace=False):
        for w in (self.replace_edit, self.replace_btn, self.replace_all_btn):
            w.setVisible(replace)
        selected = self.editor.textCursor().selectedText()
        if selected and " " not in selected:
            self.find_edit.blockSignals(True)
            self.find_edit.setText(selected)
            self.find_edit.blockSignals(False)
        self.show()
        if replace and self.find_edit.text():
            self.replace_edit.setFocus()
            self.replace_edit.selectAll()
        else:
            self.find_edit.setFocus()
            self.find_edit.selectAll()
        self.refresh()

    def close_bar(self):
        self.hide()
        set_selection_layer(self.editor, "find", [])
        self.editor.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.find_edit and event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.find_next(backward=bool(event.modifiers() & Qt.ShiftModifier))
            return True
        return False

    def _flags(self, backward=False):
        flags = QTextDocument.FindFlag(0)
        if self.case_box.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        if backward:
            flags |= QTextDocument.FindBackward
        return flags

    def _matches(self):
        text = self.find_edit.text()
        doc = self.editor.document()
        found, cursor = [], QTextCursor(doc)
        while text and len(found) < self.MAX_HIGHLIGHTS:
            cursor = doc.find(text, cursor, self._flags())
            if cursor.isNull():
                break
            found.append(QTextCursor(cursor))
        return found

    def refresh(self):
        if not self.isVisible():
            return
        matches = self._matches()
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(255, 235, 59, 150))
        fmt.setForeground(QColor("#000000"))
        set_selection_layer(self.editor, "find", [make_selection(m, fmt) for m in matches])

        if not self.find_edit.text():
            self.count_label.setText("")
        elif not matches:
            self.count_label.setText("No matches")
        else:
            cur = self.editor.textCursor().selectionStart()
            index = next((i for i, m in enumerate(matches) if m.selectionStart() == cur), None)
            total = f"{len(matches)}+" if len(matches) >= self.MAX_HIGHLIGHTS else str(len(matches))
            self.count_label.setText(f"{index + 1} of {total}" if index is not None else f"{total} matches")

    def _refresh_if_open(self):
        if self.isVisible():
            self.refresh()

    def _search_changed(self, *_):
        # Search again from where the current match starts, so typing refines in place
        c = self.editor.textCursor()
        c.setPosition(c.selectionStart())
        self.editor.setTextCursor(c)
        self.find_next()

    def find_next(self, backward=False):
        text = self.find_edit.text()
        if not text:
            self.refresh()
            return
        doc = self.editor.document()
        found = doc.find(text, self.editor.textCursor(), self._flags(backward))
        if found.isNull():
            wrap = QTextCursor(doc)
            if backward:
                wrap.movePosition(QTextCursor.End)
            found = doc.find(text, wrap, self._flags(backward))
        if not found.isNull():
            self.editor.setTextCursor(found)
            self.editor.ensureCursorVisible()
        self.refresh()

    def _selection_is_match(self):
        c = self.editor.textCursor()
        a, b = c.selectedText(), self.find_edit.text()
        return bool(b) and (a == b if self.case_box.isChecked() else a.lower() == b.lower())

    def replace_one(self):
        if self._selection_is_match():
            self.editor.textCursor().insertText(self.replace_edit.text())
        self.find_next()

    def replace_all(self):
        text = self.find_edit.text()
        if not text:
            return
        doc = self.editor.document()
        edit = QTextCursor(doc)
        edit.beginEditBlock()
        pos, count = QTextCursor(doc), 0
        while True:
            found = doc.find(text, pos, self._flags())
            if found.isNull():
                break
            edit.setPosition(found.selectionStart())
            edit.setPosition(found.selectionEnd(), QTextCursor.KeepAnchor)
            edit.insertText(self.replace_edit.text())
            pos.setPosition(edit.position())
            count += 1
        edit.endEditBlock()
        self.refresh()
        self.count_label.setText(f"Replaced {count}")
