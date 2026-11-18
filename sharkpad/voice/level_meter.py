from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QWidget


class LevelMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.level = 0
        self.trigger = 40
        self.setMinimumHeight(26)

    def set_values(self, level, trigger):
        if (level, trigger) != (self.level, self.trigger):
            self.level, self.trigger = level, trigger
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        pal = self.palette()
        p.setPen(pal.color(QPalette.Mid))
        p.setBrush(pal.color(QPalette.Base))
        p.drawRoundedRect(r, 4, 4)

        fill = QColor("#2e7d32") if self.level >= self.trigger else QColor("#9e9e9e")
        w = int(r.width() * self.level / 100)
        if w > 0:
            p.setPen(Qt.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(r.x(), r.y(), w, r.height(), 4, 4)

        x = r.x() + int(r.width() * self.trigger / 100)
        p.setPen(QPen(pal.color(QPalette.Text), 2, Qt.DashLine))
        p.drawLine(x, r.top() - 1, x, r.bottom() + 1)
        p.end()
