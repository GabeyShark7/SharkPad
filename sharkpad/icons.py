from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtSvg import QSvgRenderer

from sharkpad.paths import resource_path

ICON_SIZE = 24
_cache = {}


def _pixmap(name, color):
    key = (name, QColor(color).name())
    if key not in _cache:
        with open(resource_path(f"icons/{name}.svg"), encoding="utf-8") as f:
            svg = f.read().replace("currentColor", QColor(color).name())
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        pixmap = QPixmap(ICON_SIZE * 2, ICON_SIZE * 2)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        pixmap.setDevicePixelRatio(2)
        _cache[key] = pixmap
    return _cache[key]


def svg_icon(name, palette):
    icon = QIcon()
    icon.addPixmap(_pixmap(name, palette.color(QPalette.ButtonText)), QIcon.Normal, QIcon.Off)
    icon.addPixmap(_pixmap(name, palette.color(QPalette.HighlightedText)), QIcon.Normal, QIcon.On)
    icon.addPixmap(_pixmap(name, palette.color(QPalette.Disabled, QPalette.ButtonText)), QIcon.Disabled, QIcon.Off)
    return icon
