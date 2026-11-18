import datetime

from PySide6.QtGui import QTextCursor

PARAGRAPH_BREAK = " "


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


def insert_as_own_step(editor, text):
    """Insert text (e.g. a dictated phrase) as a separate undo step."""
    c = editor.textCursor()
    c.beginEditBlock()
    c.insertText(text)
    c.endEditBlock()
    editor.setTextCursor(c)
    editor.ensureCursorVisible()


def duplicate_line(editor):
    """Copy the current line (or the selection) right below it."""
    c = editor.textCursor()
    c.beginEditBlock()
    if c.hasSelection():
        text = c.selectedText().replace(PARAGRAPH_BREAK, "\n")
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
    lines = range_cursor(editor, start, end).selectedText().replace(PARAGRAPH_BREAK, "\n")
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
    parts = []
    if c.hasSelection():
        sel_words = len(c.selectedText().replace(PARAGRAPH_BREAK, " ").split())
        parts.append(f"{sel_words} of {words} words selected")
    else:
        parts.append(f"{words} word{'s' if words != 1 else ''}")
        parts.append(f"{len(text)} characters")
        if words >= 200:
            parts.append(f"about {round(words / 200)} min read")
    parts.append(f"Line {c.blockNumber() + 1}, Col {c.positionInBlock() + 1}")
    return "   ·   ".join(parts)
