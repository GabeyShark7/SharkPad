import json

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBitmap, QColor, QImage, QPainter, QPixmap

from sharkpad.drawing.items import ITEM_TYPES, LIGHT_BG, ImageItem

METADATA_KEY = "SharkPadDrawing"


def paint_items(painter, items, dark, skip=()):
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setRenderHint(QPainter.TextAntialiasing, True)
    for item in items:
        if item not in skip:
            item.paint(painter, dark)


def save_drawing(items, width, height, filepath):
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(LIGHT_BG)
    painter = QPainter(image)
    paint_items(painter, items, dark=False)
    painter.end()
    image.setText(METADATA_KEY, json.dumps({"v": 1, "items": [i.to_json() for i in items]}, separators=(",", ":")))
    return image.save(filepath)


def load_drawing(filepath):
    image = QImage(filepath)
    if image.isNull():
        return None
    data = image.text(METADATA_KEY)
    if data:
        try:
            return [ITEM_TYPES[d["t"]].from_json(d) for d in json.loads(data)["items"]]
        except (ValueError, KeyError, TypeError):
            pass
    pixmap = QPixmap.fromImage(image.convertToFormat(QImage.Format_ARGB32))
    pixmap.setMask(QBitmap.fromImage(image.createMaskFromColor(QColor(Qt.white).rgb(), Qt.MaskInColor)))
    return [ImageItem(pixmap, QRectF(0, 0, image.width(), image.height()), ink_raster=True)]
