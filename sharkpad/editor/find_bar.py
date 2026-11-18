from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor, QTextDocument
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from sharkpad.editor.highlights import make_selection, set_selection_layer
from sharkpad.editor.text_tools import PARAGRAPH_BREAK
from sharkpad.icons import svg_icon


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

        prev_btn = QPushButton("Previous")
        prev_btn.setToolTip("Previous match (Shift+F3 or Shift+Enter)")
        prev_btn.clicked.connect(lambda: self.find_next(backward=True))
        next_btn = QPushButton("Next")
        next_btn.setToolTip("Next match (F3 or Enter)")
        next_btn.clicked.connect(lambda: self.find_next())
        row.addWidget(prev_btn)
        row.addWidget(next_btn)

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

        self.close_btn = QPushButton()
        self.close_btn.setFixedWidth(30)
        self.close_btn.setIcon(svg_icon("x", self.palette()))
        self.close_btn.setToolTip("Close (Esc)")
        self.close_btn.setAccessibleName("Close find bar")
        self.close_btn.clicked.connect(self.close_bar)
        row.addWidget(self.close_btn)

        editor.textChanged.connect(self.refresh)
        self.hide()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange:
            self.close_btn.setIcon(svg_icon("x", self.palette()))

    def open(self, replace=False):
        for w in (self.replace_edit, self.replace_btn, self.replace_all_btn):
            w.setVisible(replace)
        selected = self.editor.textCursor().selectedText()
        if selected and PARAGRAPH_BREAK not in selected:
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

    def _search_changed(self, *_):
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
        a, b = self.editor.textCursor().selectedText(), self.find_edit.text()
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
