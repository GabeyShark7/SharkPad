from PySide6.QtGui import QTextCharFormat, QColor, QAction
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QStandardPaths
from spellchecker import SpellChecker
import os
import re

import edit_operations

# Engine Setup
spell = SpellChecker(distance=2)
ignored_words = set()           # "Ignore All": this session only

# Words with apostrophes count as one word: don't, it's, Gabe's
WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
CONTRACTION_ENDINGS = {"s", "t", "re", "ve", "ll", "d", "m"}


def _normalize(word):
    return word.replace("’", "'").lower()


def _is_known(word):
    """True if the word (any case, with or without an apostrophe ending) is spelled right."""
    w = _normalize(word)
    if w in ignored_words or spell.known([w]):
        return True
    base, apostrophe, ending = w.partition("'")
    # Possessives and contractions of known words: shark's, Mendel's, teacher'll
    return bool(apostrophe) and ending in CONTRACTION_ENDINGS and (base in ignored_words or bool(spell.known([base])))


def _skip_word(text, start, word):
    """Words we don't judge: single letters, acronyms, mixed case, and names."""
    letters = word.replace("'", "").replace("’", "")
    if len(letters) < 2:
        return True
    if letters.isupper():                       # NASA, ATP, DNA
        return True
    if any(ch.isupper() for ch in letters[1:]):  # iPhone, McDonald
        return True
    if word[0].isupper():
        # A capitalized possessive (Gabe's, Mendel's) is almost always a name
        if _normalize(word).endswith("'s"):
            return True
        # A capital in the middle of a sentence is almost always a name
        before = text[:start].rstrip(" \t\"'(“‘[")
        if before and before[-1] not in ".!?:\n ":
            return True
    return False


def find_misspellings(text, cursor_pos=-1):
    """Return [(start, end, word)] for misspelled words. The word the cursor is in
    is left alone, so it isn't flagged while you're still typing it."""
    candidates = []
    for m in WORD_RE.finditer(text):
        word = m.group()
        if m.start() <= cursor_pos <= m.end() or _skip_word(text, m.start(), word):
            continue
        candidates.append((m.start(), m.end(), word))

    verdict = {}
    for _s, _e, word in candidates:
        key = _normalize(word)
        if key not in verdict:
            verdict[key] = not _is_known(word)
    return [c for c in candidates if verdict[_normalize(c[2])]]


def suggestions(word, limit=6):
    """Best corrections first: the most common real words that are closest."""
    w = _normalize(word)
    ranked = []

    # Missing apostrophe: dont -> don't, isnt -> isn't, theyre -> they're
    for i in range(1, len(w)):
        with_apostrophe = w[:i] + "'" + w[i:]
        if spell.known([with_apostrophe]):
            ranked.append(with_apostrophe)

    freq = spell.word_frequency.dictionary
    others = (spell.candidates(w) or set()) - {w}
    ranked += sorted(others, key=lambda c: -freq.get(c, 0))

    seen, result = set(), []
    for s in ranked:
        if s not in seen:
            seen.add(s)
            result.append(s)
    result = result[:limit]

    if word[:1].isupper():
        result = [s[:1].upper() + s[1:] for s in result]
    return result


# Personal dictionary ("Add to Dictionary"), kept between sessions
def _user_dictionary_path():
    folder = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    if not folder:
        folder = os.path.join(os.path.expanduser("~"), ".sharkpad")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "dictionary.txt")


def load_user_dictionary():
    try:
        with open(_user_dictionary_path(), encoding="utf-8") as f:
            words = [line.strip() for line in f if line.strip()]
        if words:
            spell.word_frequency.load_words(words)
    except OSError:
        pass


class SpellCheckWorker(QThread):
    results_ready = Signal(list, str)  # errors + text hash for validation

    def __init__(self, text, cursor_pos=-1):
        super().__init__()
        self.text = text
        self.cursor_pos = cursor_pos

    def run(self):
        errors = find_misspellings(self.text, self.cursor_pos)
        # Send text hash to verify it hasn't changed
        self.results_ready.emit(errors, str(hash(self.text)))


_workers = set()              # running checks; old ones finish and are ignored
_last_text_hash = None


def highlight_misspelled_words(editor):
    global _last_text_hash

    if not getattr(editor, "spellcheck_enabled", True):
        edit_operations.set_selection_layer(editor, "spell", [])
        return

    current_text = editor.toPlainText()
    _last_text_hash = str(hash(current_text))

    # Only spare the word being typed when nothing is selected
    c = editor.textCursor()
    cursor_pos = -1 if c.hasSelection() else c.position()

    worker = SpellCheckWorker(current_text, cursor_pos)
    worker.results_ready.connect(lambda errs, h: apply_highlights(editor, errs, h))
    worker.finished.connect(lambda: _workers.discard(worker))
    _workers.add(worker)
    worker.start(QThread.LowPriority)


def apply_highlights(editor, errors, text_hash):
    # Only apply if text hasn't changed since we started checking
    if text_hash != _last_text_hash or not editor:
        return

    # Red wavy underlines are drawn as an overlay, not written into the text,
    # so they don't add undo steps or fire textChanged (which used to make
    # the spell check re-run itself forever)
    error_fmt = QTextCharFormat()
    error_fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)
    error_fmt.setUnderlineColor(QColor(255, 0, 0))

    selections = [
        edit_operations.make_selection(edit_operations.range_cursor(editor, start, end), error_fmt)
        for start, end, _word in errors
    ]
    edit_operations.set_selection_layer(editor, "spell", selections)


def set_spellcheck_enabled(editor, on):
    editor.spellcheck_enabled = on
    highlight_misspelled_words(editor)


def enable_spellcheck(editor):
    load_user_dictionary()
    editor.setContextMenuPolicy(Qt.CustomContextMenu)
    editor.customContextMenuRequested.connect(lambda pos: show_spellcheck_menu(editor, pos))

    timer = QTimer(editor)
    timer.setSingleShot(True)
    timer.setInterval(500)
    timer.timeout.connect(lambda: highlight_misspelled_words(editor))

    editor._spellcheck_timer = timer
    editor.textChanged.connect(timer.start)
    # Moving off a word you just typed checks it
    editor.cursorPositionChanged.connect(timer.start)

    QTimer.singleShot(500, lambda: highlight_misspelled_words(editor))


def _word_at(editor, pos):
    """The whole word (apostrophes included) under a point, as (start, end, word)."""
    cursor = editor.cursorForPosition(pos)
    block = cursor.block()
    col = cursor.positionInBlock()
    for m in WORD_RE.finditer(block.text()):
        if m.start() <= col <= m.end():
            return block.position() + m.start(), block.position() + m.end(), m.group()
    return None


def show_spellcheck_menu(editor, pos):
    found = _word_at(editor, pos)
    if not found or not getattr(editor, "spellcheck_enabled", True):
        _standard_menu(editor).exec(editor.mapToGlobal(pos))
        return
    start, end, word = found
    if _skip_word(editor.toPlainText(), start, word) or _is_known(word):
        _standard_menu(editor).exec(editor.mapToGlobal(pos))
        return

    menu = QMenu(editor)
    suggs = suggestions(word)
    if suggs:
        for i, s in enumerate(suggs):
            a = QAction(s, menu)
            if i == 0:
                f = a.font()
                f.setBold(True)  # the best guess
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
    extra = getattr(editor, "extra_context_actions", None)
    if extra:
        menu.addSeparator()
        for action in extra:
            menu.addAction(action)


def _standard_menu(editor):
    menu = editor.createStandardContextMenu()
    _add_extra_actions(editor, menu)
    return menu


def replace_word(editor, start, end, new_word):
    edit_operations.replace_range(editor, start, end, new_word)
    QTimer.singleShot(100, lambda: highlight_misspelled_words(editor))


def ignore_word(editor, word):
    ignored_words.add(_normalize(word))
    highlight_misspelled_words(editor)


def add_to_dictionary(editor, word):
    """Permanently add word to the spell checker (saved between sessions)."""
    w = _normalize(word)
    spell.word_frequency.load_words([w])
    try:
        with open(_user_dictionary_path(), "a", encoding="utf-8") as f:
            f.write(w + "\n")
    except OSError:
        pass
    highlight_misspelled_words(editor)
