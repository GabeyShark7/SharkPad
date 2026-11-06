from PySide6.QtGui import QTextCharFormat, QTextCursor, QColor, QAction
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from spellchecker import SpellChecker
import re

import edit_operations

# Engine Setup
spell = SpellChecker(distance=2)  # Increased for better recognition
ignored_words = set()

# Add common contractions and patterns that shouldn't be flagged
spell.word_frequency.load_words(['dont', 'wont', 'cant', 'shouldnt', 'wouldnt', 'couldnt', 
                                  'isnt', 'arent', 'wasnt', 'werent', 'hasnt', 'havent',
                                  'hadnt', 'doesnt', 'didnt', 'thats', 'whats', 'heres',
                                  'theres', 'youre', 'theyre', 'were', 'ive', 'youve',
                                  'weve', 'theyve', 'id', 'youd', 'hed', 'shed', 'itll',
                                  'thatll', 'ill', 'youll', 'shell', 'theyll'])

class SpellCheckWorker(QThread):
    results_ready = Signal(list, str)  # errors + text hash for validation

    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        # Only match actual alphabetic words (no numbers or mixed)
        word_regex = re.compile(r"\b[a-zA-Z]+\b")
        matches = list(word_regex.finditer(self.text))
        
        # Build set of (lowercase_word, original_case_word) pairs
        word_map = {}
        for m in matches:
            original = m.group()
            lower = original.lower()
            if lower not in ignored_words:
                if lower not in word_map:
                    word_map[lower] = []
                word_map[lower].append((m.start(), m.end(), original))
        
        # Check lowercase versions
        misspelled = spell.unknown(word_map.keys())
        
        # Map back to original positions
        errors = []
        for lower_word in misspelled:
            for start, end, original in word_map[lower_word]:
                errors.append((start, end, original))
        
        # Send text hash to verify it hasn't changed
        self.results_ready.emit(errors, str(hash(self.text)))

_workers = set()              # running checks; old ones finish and are ignored
_last_text_hash = None


def highlight_misspelled_words(editor):
    global _last_text_hash

    current_text = editor.toPlainText()
    _last_text_hash = str(hash(current_text))

    worker = SpellCheckWorker(current_text)
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

def enable_spellcheck(editor):
    editor.setContextMenuPolicy(Qt.CustomContextMenu)
    editor.customContextMenuRequested.connect(lambda pos: show_spellcheck_menu(editor, pos))
    
    timer = QTimer()
    timer.setSingleShot(True)
    timer.setInterval(700) 
    timer.timeout.connect(lambda: highlight_misspelled_words(editor))
    
    editor._spellcheck_timer = timer
    editor.textChanged.connect(timer.start)
    
    QTimer.singleShot(500, lambda: highlight_misspelled_words(editor))

def show_spellcheck_menu(editor, pos):
    cursor = editor.cursorForPosition(pos)
    cursor.select(QTextCursor.WordUnderCursor)
    word = cursor.selectedText()
    
    # Filter out non-alphabetic or ignored words
    if not word or not word.isalpha() or word.lower() in ignored_words:
        _standard_menu(editor).exec(editor.mapToGlobal(pos))
        return

    # Check lowercase version
    lower_word = word.lower()
    if lower_word not in spell.unknown([lower_word]):
        _standard_menu(editor).exec(editor.mapToGlobal(pos))
        return
    
    # Get suggestions with better matching
    suggs = list(spell.candidates(lower_word) or [])[:7]  # More suggestions
    
    # If first letter was capitalized, capitalize suggestions
    if word and word[0].isupper():
        suggs = [s.capitalize() for s in suggs]
    
    menu = QMenu(editor)
    
    # Add suggestions if available
    if suggs:
        for s in suggs:
            a = QAction(s, menu)
            a.triggered.connect(lambda _, n=s, p=pos: replace_word(editor, n, p))
            menu.addAction(a)
        menu.addSeparator()
    else:
        # If no suggestions, show a disabled item
        no_sugg = QAction("(No suggestions)", menu)
        no_sugg.setEnabled(False)
        menu.addAction(no_sugg)
        menu.addSeparator()
    
    # Always show "Ignore" option
    ignore_action = QAction(f"Ignore '{word}'", menu)
    ignore_action.triggered.connect(lambda: ignore_word(editor, word))
    menu.addAction(ignore_action)
    
    # Add "Add to Dictionary" option
    add_dict_action = QAction(f"Add '{word}' to Dictionary", menu)
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

def replace_word(editor, new_word, pos):
    cursor = editor.cursorForPosition(pos)
    cursor.select(QTextCursor.WordUnderCursor)
    cursor.insertText(new_word)
    QTimer.singleShot(100, lambda: highlight_misspelled_words(editor))

def ignore_word(editor, word):
    ignored_words.add(word.lower())  # Store as lowercase
    highlight_misspelled_words(editor)

def add_to_dictionary(editor, word):
    """Permanently add word to spellchecker dictionary"""
    spell.word_frequency.load_words([word.lower()])
    highlight_misspelled_words(editor)