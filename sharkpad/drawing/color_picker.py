from PySide6.QtCore import QEvent, QSize, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QHBoxLayout, QToolButton, QWidget

from sharkpad.icons import svg_icon

SWATCHES = [None, "#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#8e24aa", "#6d4c41"]
MAX_RECENT_COLORS = 3


def _same_color(a, b):
    if a is None or b is None:
        return a is None and b is None
    return QColor(a).name() == QColor(b).name()


class ColorPicker(QWidget):
    color_chosen = Signal()

    def __init__(self, canvas):
        super().__init__()
        self.canvas = canvas
        self.swatches = []
        self.recent_swatches = []
        self.recent_colors = []

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(5)
        for color in SWATCHES:
            swatch = self._swatch(color)
            self.swatches.append(swatch)
            row.addWidget(swatch)

        self.more = QToolButton()
        self.more.setIconSize(QSize(16, 16))
        self.more.setFixedSize(QSize(24, 24))
        self.more.setToolTip("More colors...  ·  Ctrl+Shift+C")
        self.more.setAccessibleName("More colors")
        self.more.clicked.connect(self.pick_color)
        row.addWidget(self.more)

        self.recent_row = QHBoxLayout()
        self.recent_row.setSpacing(5)
        row.addLayout(self.recent_row)
        self._restyle()
        self.mark(None)

    def _swatch(self, color):
        btn = QToolButton()
        btn.setCheckable(True)
        btn.setFixedSize(QSize(24, 24))
        btn.setProperty("swatch", color)
        btn.setToolTip("Ink (black, or white in dark mode)" if color is None else QColor(color).name())
        btn.setAccessibleName("Ink color" if color is None else f"Color {QColor(color).name()}")
        btn.clicked.connect(lambda _=False, c=color: self.choose(c))
        return btn

    def _style_swatch(self, btn):
        color = btn.property("swatch")
        fill = "palette(text)" if color is None else QColor(color).name()
        btn.setStyleSheet(
            f"QToolButton {{ background: {fill}; border: 2px solid palette(mid); border-radius: 12px; }}"
            f"QToolButton:checked {{ border: 3px solid palette(highlight); }}"
            f"QToolButton:hover {{ border: 2px solid palette(highlight); }}")

    def _restyle(self):
        self.more.setIcon(svg_icon("plus", self.palette()))
        for btn in self.swatches + self.recent_swatches:
            self._style_swatch(btn)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange:
            self._restyle()

    def mark(self, color):
        for btn in self.swatches + self.recent_swatches:
            btn.setChecked(_same_color(btn.property("swatch"), color))

    def choose(self, color):
        self.canvas.set_color(color)
        self.mark(color)
        self.color_chosen.emit()

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.canvas.color or "#000000"), self, "Pick a color")
        if color.isValid():
            self._add_recent(color.name())
            self.choose(color.name())

    def _add_recent(self, name):
        if name in [c for c in SWATCHES if c] or name in self.recent_colors:
            return
        self.recent_colors.insert(0, name)
        del self.recent_colors[MAX_RECENT_COLORS:]
        for btn in self.recent_swatches:
            btn.hide()
            btn.deleteLater()
        self.recent_swatches = [self._swatch(c) for c in self.recent_colors]
        for btn in self.recent_swatches:
            self._style_swatch(btn)
            self.recent_row.addWidget(btn)
        self.mark(self.canvas.color)
