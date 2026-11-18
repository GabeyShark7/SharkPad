import re

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QTextCharFormat

from sharkpad.editor.highlights import make_selection, set_selection_layer
from sharkpad.editor.text_tools import range_cursor, replace_range
from sharkpad.spelling.suggestions import autocorrection
from sharkpad.spelling.words import WORD_RE, no_autocorrect, normalize

AUTOCORRECT_BOUNDARY = set(" \t.,!?;:)\"")
FLASH_RGB = (229, 57, 53)
FLASH_ALPHA = 140
FLASH_HOLD_MS = 1300
FLASH_FADE_MS = 700
_WORD_AT_END = re.compile(WORD_RE.pattern + r"$")


class AutoCorrector(QObject):
    """Fixes obvious typos when a word is finished, then flashes the fix in red.

    Each fix is its own undo step, so Ctrl+Z right after puts back what was
    typed, and that word is then left alone for the rest of the session.
    """

    corrected = Signal(str, str)
    rejected = Signal(str)

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.enabled = True
        self.flashes = []
        self.last = None
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self._animate)
        editor.installEventFilter(self)
        editor.textChanged.connect(self._check_for_undo)

    def eventFilter(self, obj, event):
        if (obj is self.editor and event.type() == QEvent.KeyPress and self.enabled
                and not event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier)):
            ends_word = event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab) or (
                event.text() != "" and event.text() in AUTOCORRECT_BOUNDARY)
            c = self.editor.textCursor()
            if ends_word and not c.hasSelection():
                pos = c.position()
                QTimer.singleShot(0, lambda: self._after_word(pos))
        return False

    def _after_word(self, pos):
        doc = self.editor.document()
        if doc.characterAt(pos) not in AUTOCORRECT_BOUNDARY | {" ", "\t"}:
            return
        block = doc.findBlock(pos)
        text = block.text()
        m = _WORD_AT_END.search(text[:pos - block.position()])
        if not m:
            return
        word = m.group()
        fix = autocorrection(text, m.start(), word)
        if not fix or fix == word:
            return

        start = block.position() + m.start()
        replace_range(self.editor, start, start + len(word), fix)
        self.last = (start, word, fix)
        self._flash(start, start + len(fix))
        self.corrected.emit(word, fix)

    def _check_for_undo(self):
        if not self.last:
            return
        start, word, fix = self.last
        doc_len = self.editor.document().characterCount() - 1
        if start + len(word) > doc_len:
            return
        now = range_cursor(self.editor, start, start + len(word)).selectedText()
        if now == word and not range_cursor(self.editor, start, min(doc_len, start + len(fix))).selectedText() == fix:
            no_autocorrect.add(normalize(word))
            self.last = None
            self.flashes.clear()
            self._animate()
            self.rejected.emit(word)

    def _flash(self, start, end):
        clock = QElapsedTimer()
        clock.start()
        self.flashes.append((range_cursor(self.editor, start, end), clock))
        self._animate()
        self.timer.start()

    def _animate(self):
        selections, alive = [], []
        for cursor, clock in self.flashes:
            age = clock.elapsed()
            if age >= FLASH_HOLD_MS + FLASH_FADE_MS or not cursor.hasSelection():
                continue
            fade = 1.0 if age < FLASH_HOLD_MS else 1 - (age - FLASH_HOLD_MS) / FLASH_FADE_MS
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(*FLASH_RGB, int(FLASH_ALPHA * fade)))
            selections.append(make_selection(cursor, fmt))
            alive.append((cursor, clock))
        self.flashes = alive
        set_selection_layer(self.editor, "autocorrect", selections)
        if not alive:
            self.timer.stop()
