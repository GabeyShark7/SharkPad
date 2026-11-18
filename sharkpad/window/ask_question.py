import re

from PySide6.QtWidgets import QDialog, QMessageBox

from sharkpad.ai_teacher import teacher
from sharkpad.ai_teacher.ai_glow import ANSWER_LABEL, QUESTION_LABEL
from sharkpad.ai_teacher.ask_dialog import AskDialog
from sharkpad.editor.text_tools import PARAGRAPH_BREAK, replace_range


def qa_text(question, answer):
    answer = re.sub(r"\n\s*\n+", "\n", answer.strip())
    return f"{QUESTION_LABEL} {question}\n{ANSWER_LABEL} {answer}"


class AskQuestion:
    def __init__(self, win):
        self.win = win
        self.waiting = 0

    def open(self):
        win = self.win
        editor = win.editor
        c = editor.textCursor()
        text = editor.toPlainText()
        if c.hasSelection():
            passage, end = c.selectedText().replace(PARAGRAPH_BREAK, "\n"), c.selectionEnd()
        else:
            passage, end = text, len(text)
        if not passage.strip():
            QMessageBox.information(win, "Ask a Question", "Highlight some notes first, then ask about them.")
            return
        dialog = AskDialog(win, passage)
        if dialog.exec() != QDialog.Accepted:
            return
        question = dialog.question()
        self.waiting += 1
        self._show_waiting()
        teacher.run_async(lambda: teacher.answer_question(question, passage),
                          lambda ok, answer: self._answered(ok, answer, question, passage, end, text))

    def _show_waiting(self):
        if self.waiting:
            count = f"{self.waiting} questions" if self.waiting > 1 else "your question"
            self.win.status_bar.showMessage(f"AI Teacher is answering {count}... you can keep working.")

    def _insert_point(self, passage, end, text_at_start):
        current = self.win.editor.toPlainText()
        if current != text_at_start:
            found = current.find(passage)
            end = found + len(passage) if found >= 0 else len(current)
        line_end = current.find("\n", end)
        return len(current) if line_end < 0 else line_end, current

    def _answered(self, ok, answer, question, passage, end, text_at_start):
        win = self.win
        self.waiting -= 1
        if not ok:
            win.status_bar.clearMessage()
            QMessageBox.warning(win, "AI Teacher", answer)
            return
        pos, current = self._insert_point(passage, end, text_at_start)
        block = "\n\n" + qa_text(question, answer) + ("\n" if pos < len(current) else "")
        replace_range(win.editor, pos, pos, block)
        win.status_bar.showMessage("Answer added below your notes. Ctrl+Z removes it.", 6000)
        self._show_waiting()
