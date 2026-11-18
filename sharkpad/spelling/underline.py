import threading

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QTextCharFormat
from PySide6.QtWidgets import QMenu

from sharkpad.editor.highlights import make_selection, set_selection_layer
from sharkpad.editor.text_tools import range_cursor, replace_range
from sharkpad.spelling import words
from sharkpad.spelling.suggestions import build_word_indexes, suggestions


class SpellCheckWorker(QThread):
    results_ready = Signal(list, str)

    def __init__(self, text, cursor_pos=-1):
        super().__init__()
        self.text = text
        self.cursor_pos = cursor_pos

    def run(self):
        errors = words.find_misspellings(self.text, self.cursor_pos)
        self.results_ready.emit(errors, str(hash(self.text)))


_workers = set()
_last_text_hash = None


def highlight_misspelled_words(editor):
    global _last_text_hash

    if not editor.spellcheck_enabled:
        set_selection_layer(editor, "spell", [])
        return

    current_text = editor.toPlainText()
    _last_text_hash = str(hash(current_text))

    c = editor.textCursor()
    cursor_pos = -1 if c.hasSelection() else c.position()

    worker = SpellCheckWorker(current_text, cursor_pos)
    worker.results_ready.connect(lambda errs, h: apply_highlights(editor, errs, h))
    worker.finished.connect(lambda: _workers.discard(worker))
    _workers.add(worker)
    worker.start(QThread.LowPriority)


def apply_highlights(editor, errors, text_hash):
    if text_hash != _last_text_hash:
        return

    error_fmt = QTextCharFormat()
    error_fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)
    error_fmt.setUnderlineColor(QColor(255, 0, 0))

    selections = [make_selection(range_cursor(editor, start, end), error_fmt) for start, end, _word in errors]
    set_selection_layer(editor, "spell", selections)


def set_spellcheck_enabled(editor, on):
    editor.spellcheck_enabled = on
    highlight_misspelled_words(editor)


def enable_spellcheck(editor):
    words.load_user_dictionary()
    threading.Thread(target=build_word_indexes, daemon=True).start()
    editor.setContextMenuPolicy(Qt.CustomContextMenu)
    editor.customContextMenuRequested.connect(lambda pos: show_spellcheck_menu(editor, pos))

    timer = QTimer(editor)
    timer.setSingleShot(True)
    timer.setInterval(500)
    timer.timeout.connect(lambda: highlight_misspelled_words(editor))
    editor.textChanged.connect(timer.start)
    editor.cursorPositionChanged.connect(timer.start)

    QTimer.singleShot(500, lambda: highlight_misspelled_words(editor))


def _word_at(editor, pos):
    """The whole word (apostrophes included) under a point, as (start, end, word)."""
    cursor = editor.cursorForPosition(pos)
    block = cursor.block()
    col = cursor.positionInBlock()
    for m in words.WORD_RE.finditer(block.text()):
        if m.start() <= col <= m.end():
            return block.position() + m.start(), block.position() + m.end(), m.group()
    return None


def show_spellcheck_menu(editor, pos):
    found = _word_at(editor, pos)
    if not found or not editor.spellcheck_enabled:
        _standard_menu(editor).exec(editor.mapToGlobal(pos))
        return
    start, end, word = found
    if words.skip_word(editor.toPlainText(), start, word) or words.is_known(word):
        _standard_menu(editor).exec(editor.mapToGlobal(pos))
        return

    menu = QMenu(editor)
    suggs = suggestions(word)
    if suggs:
        for i, s in enumerate(suggs):
            a = QAction(s, menu)
            if i == 0:
                f = a.font()
                f.setBold(True)
                a.setFont(f)
            a.triggered.connect(lambda _=False, n=s: replace_word(editor, start, end, n))
            menu.addAction(a)
    else:
        no_sugg = QAction("(No suggestions)", menu)
        no_sugg.setEnabled(False)
        menu.addAction(no_sugg)
    menu.addSeparator()

    ignore_action = QAction(f"Ignore All \"{word}\"", menu)
    ignore_action.triggered.connect(lambda: ignore_word(editor, word))
    menu.addAction(ignore_action)

    add_dict_action = QAction(f"Add \"{word}\" to Dictionary", menu)
    add_dict_action.triggered.connect(lambda: add_to_dictionary(editor, word))
    menu.addAction(add_dict_action)
    _add_extra_actions(editor, menu)

    menu.exec(editor.mapToGlobal(pos))


def _add_extra_actions(editor, menu):
    if editor.extra_context_actions:
        menu.addSeparator()
        for action in editor.extra_context_actions:
            menu.addAction(action)


def _standard_menu(editor):
    menu = editor.createStandardContextMenu()
    _add_extra_actions(editor, menu)
    return menu


def replace_word(editor, start, end, new_word):
    replace_range(editor, start, end, new_word)
    QTimer.singleShot(100, lambda: highlight_misspelled_words(editor))


def ignore_word(editor, word):
    words.ignored_words.add(words.normalize(word))
    highlight_misspelled_words(editor)


def add_to_dictionary(editor, word):
    words.add_to_dictionary(word)
    highlight_misspelled_words(editor)
