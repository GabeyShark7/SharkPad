from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QFontMetricsF
from PySide6.QtWidgets import QFrame, QPlainTextEdit

from sharkpad.drawing.items import ink


class TextBox(QPlainTextEdit):
    done = Signal()

    def __init__(self, canvas, item):
        super().__init__(canvas)
        self.item = item
        self._finished = False
        self.setFrameStyle(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.document().setDocumentMargin(0)
        self.setFont(item.font())
        self.setAccessibleName("Drawing pad text")
        self.setPlainText(item.text)
        self.textChanged.connect(self.fit)
        self.restyle(canvas.dark)
        self.fit()

    def restyle(self, dark):
        color = ink(self.item.color, dark).name()
        self.setStyleSheet(
            f"QPlainTextEdit {{ background: transparent; color: {color}; border: 1px dashed palette(highlight); }}")

    def fit(self):
        fm = QFontMetricsF(self.font())
        lines = self.toPlainText().split("\n")
        width = max([fm.horizontalAdvance(line) for line in lines] + [fm.horizontalAdvance("M") * 4])
        canvas = self.parentWidget()
        self.setGeometry(round(self.item.x) - 3, round(self.item.y) - 3,
                         min(round(width) + 24, canvas.width() - round(self.item.x) + 3),
                         round(fm.lineSpacing() * len(lines)) + 8)

    def event(self, event):
        if event.type() == QEvent.ShortcutOverride and event.key() == Qt.Key_Escape:
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape or (event.key() in (Qt.Key_Return, Qt.Key_Enter)
                                            and event.modifiers() & Qt.ControlModifier):
            self.finish()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        QTimer.singleShot(0, self.finish)

    def finish(self):
        if not self._finished:
            self._finished = True
            self.done.emit()
