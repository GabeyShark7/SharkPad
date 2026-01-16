from PySide6.QtGui import QTextCharFormat, QTextCursor, QColor, QAction
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Qt, QTimer
import language_tool_python
import re

# ---------------------------
# Initialize LanguageTool
# ---------------------------
tool = language_tool_python.LanguageTool('en-US')

# Preload to avoid first-time freeze
QTimer.singleShot(0, lambda: tool.check(" "))

# ---------------------------
# Ignored words
# ---------------------------
ignored_words = set()

# ---------------------------
# Highlight function
# ---------------------------
def highlight_misspelled_words(editor):
    doc = editor.document()
    cursor = QTextCursor(doc)
    cursor.select(QTextCursor.Document)
    cursor.setCharFormat(QTextCharFormat())

    text = editor.toPlainText()
    if not text.strip():
        return

    word_regex = re.compile(r"\b\w+\b")

    try:
        matches = tool.check(text)
    except Exception:
        matches = []

    error_positions = []
    for m in matches:
        start, end = m.offset, m.offset + m.error_length
        error_positions.append((start, end, tuple(m.replacements)))

    block = doc.firstBlock()
    while block.isValid():
        block_text = block.text()
        block_pos = block.position()

        for match in word_regex.finditer(block_text):
            start = block_pos + match.start()
            end = block_pos + match.end()
            word = match.group()

            if word in ignored_words:
                continue

            for err_start, err_end, replacements in error_positions:
                if start < err_end and end > err_start:
                    fmt = QTextCharFormat()
                    fmt.setBackground(QColor(255, 0, 0))       # RED highlight
                    fmt.setForeground(QColor(255, 255, 255))   # White text
                    word_cursor = QTextCursor(doc)
                    word_cursor.setPosition(start)
                    word_cursor.setPosition(end, QTextCursor.KeepAnchor)
                    word_cursor.setCharFormat(fmt)
                    break

        block = block.next()

# ---------------------------
# Right-click context menu
# ---------------------------
def show_spellcheck_menu(editor, position):
    cursor = editor.cursorForPosition(position)
    cursor.select(QTextCursor.WordUnderCursor)
    word = cursor.selectedText()
    word_start = cursor.selectionStart()
    word_end = cursor.selectionEnd()

    print(f"DEBUG: Right-clicked word: '{word}' at positions {word_start}-{word_end}")

    if not word or word in ignored_words:
        print(f"DEBUG: Word is empty or ignored")
        return

    text = editor.toPlainText()
    try:
        matches = tool.check(text)
    except Exception:
        matches = []

    print(f"DEBUG: Total matches found: {len(matches)}")

    # Find matches that overlap with the clicked word position
    suggestions = []
    for m in matches:
        match_start = m.offset
        match_end = m.offset + m.error_length
        
        # Check if the match overlaps with our word position
        if match_start <= word_start < match_end or word_start <= match_start < word_end:
            print(f"DEBUG: Found matching error at {match_start}-{match_end}")
            print(f"DEBUG: Replacements: {m.replacements}")
            suggestions.extend(m.replacements)
            break

    suggestions = list(dict.fromkeys(suggestions))  # remove duplicates
    print(f"DEBUG: Suggestions after dedup: {suggestions}")
    suggestions = suggestions[:5]  # top 5
    print(f"DEBUG: Final suggestions (top 5): {suggestions}")

    menu = QMenu(editor)
    print(f"DEBUG: Creating menu with {len(suggestions)} suggestions")
    
    if suggestions:
        for i, suggestion in enumerate(suggestions):
            print(f"DEBUG: Adding action {i}: '{suggestion}'")
            action = QAction(suggestion, menu)
            action.triggered.connect(lambda checked=False, s=suggestion, start=word_start, end=word_end: 
                                    replace_word(editor, start, end, s))
            menu.addAction(action)
    else:
        action = QAction("No suggestions", menu)
        action.setDisabled(True)
        menu.addAction(action)

    menu.addSeparator()
    ignore_action = QAction("Ignore", menu)
    ignore_action.triggered.connect(lambda: ignore_word(editor, word))
    menu.addAction(ignore_action)

    print(f"DEBUG: About to show menu with {len(menu.actions())} actions")
    menu.exec(editor.mapToGlobal(position))
    print(f"DEBUG: Menu closed")


# ---------------------------
# Replace word
# ---------------------------
def replace_word(editor, start, end, new_word):
    print(f"DEBUG: replace_word called with '{new_word}' at {start}-{end}")
    cursor = editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.KeepAnchor)
    cursor.insertText(new_word)
    highlight_misspelled_words(editor)

# ---------------------------
# Ignore word
# ---------------------------
def ignore_word(editor, word):
    print(f"DEBUG: Ignoring word '{word}'")
    ignored_words.add(word)
    highlight_misspelled_words(editor)

# ---------------------------
# Enable spellcheck
# ---------------------------
def enable_spellcheck(editor):
    editor.setContextMenuPolicy(Qt.CustomContextMenu)
    editor.customContextMenuRequested.connect(lambda pos: show_spellcheck_menu(editor, pos))

    timer = QTimer()
    timer.setSingleShot(True)
    timer.setInterval(300)

    def schedule_highlight():
        timer.start()

    timer.timeout.connect(lambda: highlight_misspelled_words(editor))
    editor.textChanged.connect(schedule_highlight)

    highlight_misspelled_words(editor)