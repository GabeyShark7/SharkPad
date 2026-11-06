from PySide6.QtGui import QTextCharFormat, QColor, QAction
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QStandardPaths, QObject, QEvent, QElapsedTimer
from spellchecker import SpellChecker
import os
import re

import edit_operations

# Engine Setup
spell = SpellChecker(distance=2)
ignored_words = set()           # "Ignore All": this session only
no_autocorrect = set()          # words the user un-did an autocorrect on (this session)

# Everyday words the built-in dictionary is missing, so they're never
# underlined or "corrected" into something else (lol -> lot, wifi -> wife)
spell.word_frequency.load_words([
    "lol", "lmao", "omg", "idk", "tbh", "brb", "btw", "fyi", "asap", "aka", "diy", "faq", "irl",
    "imo", "smh", "ngl", "jk", "ty", "thx", "pls", "plz", "ok", "okay", "gonna", "wanna", "gotta",
    "wifi", "app", "apps", "api", "apis", "cpu", "gpu", "ram", "usb", "pdf", "pdfs", "url", "urls",
    "html", "css", "email", "emails", "online", "offline", "login", "logout", "username", "website",
    "blog", "vlog", "podcast", "selfie", "emoji", "emojis", "meme", "memes", "youtube", "tiktok",
    "instagram", "google", "github", "python", "javascript", "java", "laptop", "smartphone",
    "covid", "etc", "vs", "eg", "ie", "mol", "lim", "sin", "cos", "tan", "dx", "dy", "kg", "km",
    "cm", "mm", "ml", "mg", "hz", "kj", "dna", "rna", "atp", "adp", "nadh", "nadph", "ph",
])

# Classic typos that a frequency guess gets wrong or isn't sure about
COMMON_TYPOS = {
    "i": "I", "im": "I'm", "ive": "I've", "ill": None, "id": None, "alot": "a lot",
    "teh": "the", "hte": "the", "wich": "which", "whihc": "which", "becuase": "because",
    "becasue": "because", "beacuse": "because", "recieve": "receive", "recieved": "received",
    "beleive": "believe", "freind": "friend", "thier": "their", "untill": "until",
    "occured": "occurred", "seperate": "separate", "definately": "definitely", "wierd": "weird",
    "tommorow": "tomorrow", "tomorow": "tomorrow", "truely": "truly", "goverment": "government",
    "enviroment": "environment", "accomodate": "accommodate", "acheive": "achieve",
    "arguement": "argument", "calender": "calendar", "concious": "conscious", "existance": "existence",
    "foriegn": "foreign", "independant": "independent", "occurence": "occurrence",
    "posession": "possession", "publically": "publicly", "succesful": "successful",
    "suprise": "surprise", "tounge": "tongue", "wether": "whether", "writting": "writing",
}

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


_contractions = None


def _apostrophe_fix(w):
    """dont -> don't, theyre -> they're (or None)."""
    global _contractions
    if _contractions is None:
        _contractions = {c.replace("'", ""): c for c in spell.word_frequency.dictionary if "'" in c}
    return _contractions.get(w)


def _transpositions(w):
    return {w[:i] + w[i + 1] + w[i] + w[i + 2:] for i in range(len(w) - 1)}


def _match_case(original, fix):
    if original[:1].isupper() and fix[:1].islower():
        return fix[:1].upper() + fix[1:]
    return fix


AUTOCORRECT_MIN_FREQ = 500      # only correct into reasonably common words
AUTOCORRECT_RATIO = 3           # ...that are clearly likelier than the runner-up


def autocorrection(text, start, word):
    """The confident fix for a just-typed word, or None to leave it alone.

    Only fixes obvious typos into common words. Anything uncertain is left
    for the red underline and right-click suggestions instead.
    """
    w = _normalize(word)
    if w in no_autocorrect or w in ignored_words:
        return None
    if w in COMMON_TYPOS:
        fix = COMMON_TYPOS[w]
        return _match_case(word, fix) if fix else None
    if _skip_word(text, start, word) or _is_known(word) or not w.isalpha():
        return None

    fix = _apostrophe_fix(w)
    if fix:
        return _match_case(word, fix)

    freq = spell.word_frequency.dictionary
    swaps = spell.known(_transpositions(w))

    if len(w) <= 4:
        # Short words have too many look-alikes; only fix swapped letters (teh, hwo)
        cands = {c: freq[c] for c in swaps}
    else:
        d1 = spell.edit_distance_1(w)
        cands = {c: freq[c] for c in spell.known(d1)}
        for e in d1:  # one slip away from a contraction: diont -> dont -> don't
            f = _apostrophe_fix(e)
            if f:
                cands[f] = max(cands.get(f, 0), freq.get(f, 0))

    need = AUTOCORRECT_MIN_FREQ
    if not cands and len(w) >= 6:
        cands = {c: freq[c] for c in spell.known(spell.edit_distance_2(w))}
        need *= 4  # two slips away: only fix into very common words
    if not cands:
        return None

    # Swapped letters (liek, taht) are the most common typo, so they get a boost,
    # but a much more common word still wins (realy -> really, not relay)
    score = {c: f * (5 if c in swaps else 1) for c, f in cands.items()}
    ranked = sorted(score.values(), reverse=True)
    best = max(score, key=score.get)
    runner_up = ranked[1] if len(ranked) > 1 else 0
    if cands[best] < need or score[best] < AUTOCORRECT_RATIO * runner_up:
        return None
    return _match_case(word, best)


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


# Autocorrect while typing (like Google Docs)
AUTOCORRECT_BOUNDARY = set(" \t.,!?;:)\"")
FLASH_RGB = (229, 57, 53)       # red highlighter
FLASH_ALPHA = 140
FLASH_HOLD_MS = 1300
FLASH_FADE_MS = 700
_WORD_AT_END = re.compile(WORD_RE.pattern + r"$")


class AutoCorrector(QObject):
    """Fixes obvious typos when a word is finished, then flashes the fix in red.

    Each fix is its own undo step, so Ctrl+Z right after puts back what was
    typed, and that word is then left alone for the rest of the session.
    """

    corrected = Signal(str, str)    # what was typed, what it became
    rejected = Signal(str)          # the user undid a fix of this word

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.enabled = True
        self.flashes = []           # [(QTextCursor over the fix, QElapsedTimer)]
        self.last = None            # (start, typed word, fix)
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
                # The word ends where the cursor is now; check it once the key's
                # character has been inserted
                pos = c.position()
                QTimer.singleShot(0, lambda: self._after_word(pos))
        return False

    def _after_word(self, pos):
        doc = self.editor.document()
        if doc.characterAt(pos) not in AUTOCORRECT_BOUNDARY | {"\u2029", "\t"}:
            return                     # the key didn't insert anything here
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
        edit_operations.replace_range(self.editor, start, start + len(word), fix)
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
        now = edit_operations.range_cursor(self.editor, start, start + len(word)).selectedText()
        if now == word and not edit_operations.range_cursor(
                self.editor, start, min(doc_len, start + len(fix))).selectedText() == fix:
            no_autocorrect.add(_normalize(word))
            self.last = None
            self.flashes.clear()
            self._animate()
            self.rejected.emit(word)

    def _flash(self, start, end):
        clock = QElapsedTimer()
        clock.start()
        self.flashes.append((edit_operations.range_cursor(self.editor, start, end), clock))
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
            selections.append(edit_operations.make_selection(cursor, fmt))
            alive.append((cursor, clock))
        self.flashes = alive
        edit_operations.set_selection_layer(self.editor, "autocorrect", selections)
        if not alive:
            self.timer.stop()
