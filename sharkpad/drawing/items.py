import base64
import math

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainterPath, QPen, QPixmap

LIGHT_BG = QColor("#ffffff")
DARK_BG = QColor("#1e1e1e")
LIGHT_INK = QColor(Qt.black)
DARK_INK = QColor(Qt.white)

HIGHLIGHT_DEFAULT = "#fdd835"
HIGHLIGHT_ALPHA = 95
POINT_SPACING = 2.0


def ink(color, dark):
    if color is None:
        return QColor(DARK_INK if dark else LIGHT_INK)
    return QColor(color)


def swap_default_ink(pixmap, to_dark):
    src = LIGHT_INK if to_dark else DARK_INK
    dst = DARK_INK if to_dark else LIGHT_INK
    img = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    src_rgb = src.rgb() & 0xFFFFFF
    for y in range(img.height()):
        for x in range(img.width()):
            px = img.pixel(x, y)
            alpha = (px >> 24) & 0xFF
            if alpha and (px & 0xFFFFFF) == src_rgb:
                img.setPixel(x, y, (alpha << 24) | (dst.rgb() & 0xFFFFFF))
    return QPixmap.fromImage(img)


def _pixmap_to_b64(pixmap):
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    return base64.b64encode(bytes(data)).decode("ascii")


def _pixmap_from_b64(text):
    pixmap = QPixmap()
    pixmap.loadFromData(base64.b64decode(text), "PNG")
    return pixmap


class Stroke:
    def __init__(self, points, color, width, highlight=False):
        self.points = points
        self.color = color
        self.width = width
        self.highlight = highlight
        self._bounds = None
        self._path = None

    def clone(self):
        return Stroke(list(self.points), self.color, self.width, self.highlight)

    def changed(self):
        self._bounds = None
        self._path = None

    def add_point(self, x, y):
        lx, ly = self.points[-1]
        dist = math.hypot(x - lx, y - ly)
        if dist < POINT_SPACING:
            return False
        steps = int(dist // POINT_SPACING)
        for i in range(1, steps + 1):
            t = i / steps
            self.points.append((lx + (x - lx) * t, ly + (y - ly) * t))
        self.changed()
        return True

    def bounds(self):
        if self._bounds is None:
            xs = [p[0] for p in self.points]
            ys = [p[1] for p in self.points]
            pad = self.width / 2 + 1
            self._bounds = QRectF(min(xs) - pad, min(ys) - pad, max(xs) - min(xs) + 2 * pad, max(ys) - min(ys) + 2 * pad)
        return self._bounds

    def path(self):
        if self._path is None:
            pts = self.points
            path = QPainterPath(QPointF(*pts[0]))
            if len(pts) == 1:
                path.lineTo(pts[0][0] + 0.01, pts[0][1])
            else:
                for i in range(1, len(pts) - 1):
                    mid = QPointF((pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2)
                    path.quadTo(QPointF(*pts[i]), mid)
                path.lineTo(QPointF(*pts[-1]))
            self._path = path
        return self._path

    def paint(self, painter, dark):
        color = ink(self.color, dark)
        if self.highlight:
            color.setAlpha(HIGHLIGHT_ALPHA)
        painter.setPen(QPen(color, self.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

    def hit(self, x, y, tolerance=4):
        if not self.bounds().adjusted(-tolerance, -tolerance, tolerance, tolerance).contains(QPointF(x, y)):
            return False
        reach = (self.width / 2 + tolerance) ** 2
        return any((px - x) ** 2 + (py - y) ** 2 <= reach for px, py in self.points)

    def in_rect(self, rect):
        if not rect.intersects(self.bounds()):
            return False
        return any(rect.contains(QPointF(px, py)) for px, py in self.points)

    def transform(self, fn, scale):
        self.points = [fn(px, py) for px, py in self.points]
        self.width = max(1.0, self.width * scale)
        self.changed()

    def to_json(self):
        return {"t": "stroke", "pts": [[round(x, 1), round(y, 1)] for x, y in self.points],
                "c": self.color, "w": self.width, "hl": self.highlight}

    @staticmethod
    def from_json(d):
        return Stroke([tuple(p) for p in d["pts"]], d.get("c"), d.get("w", 3), d.get("hl", False))


class ImageItem:
    def __init__(self, pixmap, rect, ink_raster=False):
        self.pixmap = pixmap
        self.rect = QRectF(rect)
        self.ink_raster = ink_raster
        self._dark_pixmap = None

    def clone(self):
        item = ImageItem(self.pixmap, self.rect, self.ink_raster)
        item._dark_pixmap = self._dark_pixmap
        return item

    def bounds(self):
        return QRectF(self.rect)

    def paint(self, painter, dark):
        pixmap = self.pixmap
        if self.ink_raster and dark:
            if self._dark_pixmap is None:
                self._dark_pixmap = swap_default_ink(self.pixmap, to_dark=True)
            pixmap = self._dark_pixmap
        painter.drawPixmap(self.rect, pixmap, QRectF(pixmap.rect()))

    def hit(self, x, y):
        return self.rect.contains(QPointF(x, y))

    def in_rect(self, rect):
        return rect.intersects(self.rect)

    def transform(self, fn, scale):
        x1, y1 = fn(self.rect.left(), self.rect.top())
        x2, y2 = fn(self.rect.right(), self.rect.bottom())
        self.rect = QRectF(QPointF(x1, y1), QPointF(x2, y2)).normalized()

    def to_json(self):
        r = self.rect
        return {"t": "image", "png": _pixmap_to_b64(self.pixmap), "r": [r.x(), r.y(), r.width(), r.height()],
                "ink": self.ink_raster}

    @staticmethod
    def from_json(d):
        return ImageItem(_pixmap_from_b64(d["png"]), QRectF(*d["r"]), d.get("ink", False))


class TextItem:
    def __init__(self, x, y, text, color, size):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.size = size

    def clone(self):
        return TextItem(self.x, self.y, self.text, self.color, self.size)

    def font(self):
        font = QFont("Arial")
        font.setPixelSize(max(6, round(self.size)))
        return font

    def bounds(self):
        fm = QFontMetricsF(self.font())
        lines = self.text.split("\n")
        width = max([fm.horizontalAdvance(line) for line in lines] + [4])
        return QRectF(self.x - 2, self.y - 2, width + 4, fm.lineSpacing() * len(lines) + 4)

    def paint(self, painter, dark):
        painter.setFont(self.font())
        painter.setPen(ink(self.color, dark))
        fm = QFontMetricsF(self.font())
        for i, line in enumerate(self.text.split("\n")):
            painter.drawText(QPointF(self.x, self.y + fm.ascent() + i * fm.lineSpacing()), line)

    def hit(self, x, y, tolerance=2):
        return self.bounds().adjusted(-tolerance, -tolerance, tolerance, tolerance).contains(QPointF(x, y))

    def in_rect(self, rect):
        return rect.intersects(self.bounds())

    def transform(self, fn, scale):
        self.x, self.y = fn(self.x, self.y)
        self.size = max(6.0, self.size * scale)

    def to_json(self):
        return {"t": "text", "x": self.x, "y": self.y, "s": self.text, "c": self.color, "pt": self.size}

    @staticmethod
    def from_json(d):
        return TextItem(d["x"], d["y"], d["s"], d.get("c"), d.get("pt", 20))


ITEM_TYPES = {"stroke": Stroke, "image": ImageItem, "text": TextItem}
