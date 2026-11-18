from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPalette
from PySide6.QtWidgets import QPlainTextEdit, QWidget


class _LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_numbers(event)


class NotesEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_numbers_visible = True
        self.spellcheck_enabled = True
        self.extra_context_actions = []
        self._number_area = _LineNumberArea(self)
        self._number_width = 0
        self._last_block = -1
        self._refresh_number_font()
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._update_area)
        self.cursorPositionChanged.connect(self._cursor_moved)
        self._update_margin()

    def set_line_numbers(self, on):
        self.line_numbers_visible = on
        self._number_area.setVisible(on)
        self._update_margin()

    def _refresh_number_font(self):
        font = QFont(self.font())
        font.setPointSizeF(max(7.0, self.font().pointSizeF() * 0.75))
        font.setBold(False)
        font.setLetterSpacing(QFont.PercentageSpacing, 100)
        self._number_font = font
        self._number_digit = QFontMetrics(font).horizontalAdvance("9")

    def line_number_width(self):
        if not self.line_numbers_visible:
            return 0
        digits = max(2, len(str(self.blockCount())))
        return 10 + self._number_digit * digits

    def _update_margin(self, *_):
        width = self.line_number_width()
        if width != self._number_width:
            self._number_width = width
            self.setViewportMargins(width, 0, 0, 0)
            self._place_number_area()

    def _place_number_area(self):
        cr = self.contentsRect()
        self._number_area.setGeometry(QRect(cr.left(), cr.top(), self._number_width, cr.height()))

    def _update_area(self, rect, dy):
        if not self.line_numbers_visible:
            return
        if dy:
            self._number_area.scroll(0, dy)
        else:
            self._number_area.update(0, rect.y(), self._number_area.width(), rect.height())

    def _cursor_moved(self):
        block = self.textCursor().blockNumber()
        if block != self._last_block:
            self._last_block = block
            self._number_area.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_number_area()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.FontChange:
            self._refresh_number_font()
            self._number_width = -1
            self._update_margin()

    def paint_line_numbers(self, event):
        painter = QPainter(self._number_area)
        palette = self.palette()
        painter.fillRect(event.rect(), palette.color(QPalette.Base))
        painter.setFont(self._number_font)
        dim, bright = palette.color(QPalette.PlaceholderText), palette.color(QPalette.Text)
        current = self.textCursor().blockNumber()
        width = self._number_area.width() - 6
        line_height = self.fontMetrics().height()
        clip_top, clip_bottom = event.rect().top(), event.rect().bottom()

        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= clip_bottom:
            bottom = top + round(self.blockBoundingRect(block).height())
            if block.isVisible() and bottom >= clip_top:
                number = block.blockNumber()
                painter.setPen(bright if number == current else dim)
                painter.drawText(0, top, width, line_height, Qt.AlignRight | Qt.AlignVCenter, str(number + 1))
            block = block.next()
            top = bottom
        painter.end()
