import re

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QColor, QFont, QTextCharFormat

from sharkpad.ai_teacher.instructions import find_blocks, marker_spans
from sharkpad.editor.highlights import make_selection, set_selection_layer
from sharkpad.editor.text_tools import range_cursor

QUESTION_LABEL = "[Asked]"
ANSWER_LABEL = "[AI Teacher]"
QA_RE = re.compile(r"^\[Asked\] .*(?:\n(?![ \t]*$).*)*", re.M)
LABEL_RE = re.compile(r"^(?:\[Asked\]|\[AI Teacher\])", re.M)

INSTRUCT_GLOW = QColor(229, 57, 53, 45)
INSTRUCT_MARKER = QColor(229, 57, 53, 110)
INSTRUCT_TEXT = QColor("#c62828")
QA_GLOW = QColor(30, 136, 229, 50)
QA_LABEL = QColor("#1565c0")


def _format(background, foreground=None, bold=False):
    fmt = QTextCharFormat()
    fmt.setBackground(background)
    if foreground is not None:
        fmt.setForeground(foreground)
    if bold:
        fmt.setFontWeight(QFont.Bold)
    return fmt


class AiGlow(QObject):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.refresh)
        editor.textChanged.connect(self.timer.start)
        self.refresh()

    def _spans(self, spans, fmt):
        return [make_selection(range_cursor(self.editor, s, e), fmt) for s, e in spans]

    def refresh(self):
        text = self.editor.toPlainText()
        instruct = []
        if "AI-INSTRUCT" in text:
            instruct = self._spans([(b.start, b.end) for b in find_blocks(text)], _format(INSTRUCT_GLOW))
            instruct += self._spans(marker_spans(text), _format(INSTRUCT_MARKER, INSTRUCT_TEXT, bold=True))
        set_selection_layer(self.editor, "instruct", instruct)

        qa = []
        if QUESTION_LABEL in text:
            qa = self._spans([m.span() for m in QA_RE.finditer(text)], _format(QA_GLOW))
            qa += self._spans([m.span() for m in LABEL_RE.finditer(text)], _format(QA_GLOW, QA_LABEL, bold=True))
        set_selection_layer(self.editor, "qa", qa)
