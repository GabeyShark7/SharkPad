import base64
import json
import math

from PySide6.QtCore import QBuffer, QByteArray, QEvent, QIODevice, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBitmap, QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPalette, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup, QColorDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QSlider, QToolButton, QVBoxLayout, QWidget,
)

import edit_operations

pad_size_width = 450
pad_size_height = 400

LIGHT_BG = QColor("#ffffff")
DARK_BG = QColor("#1e1e1e")
LIGHT_INK = QColor(Qt.black)
DARK_INK = QColor(Qt.white)

METADATA_KEY = "SharkPadDrawing"
SWATCHES = [None, "#e53935", "#fb8c00", "#fdd835", "#43a047", "#1e88e5", "#8e24aa", "#6d4c41"]
HIGHLIGHT_DEFAULT = "#fdd835"
HIGHLIGHT_ALPHA = 95
TOOL_SIZES = {"draw": (1, 40, 3), "highlight": (6, 48, 18), "erase": (4, 80, 18), "text": (8, 72, 20)}
TOOL_HINTS = {
    "select": "Drag a box to select · Shift+click adds · Drag corners to resize · Delete removes",
    "draw": "Draw with your mouse or pen",
    "highlight": "Highlight over your drawing",
    "erase": "Rub over lines to erase them",
    "text": "Click to type · Click away or press Esc when done · Double-click text to edit it",
}
HANDLE = 8
POINT_SPACING = 2.0


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


def _ink(color, dark):
    if color is None:
        return QColor(DARK_INK if dark else LIGHT_INK)
    return QColor(color)


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
    kind = "stroke"

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
        color = _ink(self.color, dark)
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
    kind = "image"

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

    def hit(self, x, y, tolerance=0):
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
    kind = "text"

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
        painter.setPen(_ink(self.color, dark))
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


class _TextBox(QPlainTextEdit):
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
        self.textChanged.connect(self._fit)
        self.restyle(canvas.dark)
        self._fit()

    def restyle(self, dark):
        color = _ink(self.item.color, dark).name()
        self.setStyleSheet(
            f"QPlainTextEdit {{ background: transparent; color: {color}; border: 1px dashed palette(highlight); }}")

    def _fit(self):
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


class DrawingCanvas(QWidget):
    changed = Signal()
    selection_changed = Signal()
    tool_changed = Signal(str)
    appearance_changed = Signal()
    MAX_UNDO = 50

    def __init__(self, width=pad_size_width, height=pad_size_height):
        super().__init__()
        self.setFixedSize(width, height)
        self.canvas_width = width
        self.canvas_height = height
        self.setFocusPolicy(Qt.ClickFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("Drawing canvas")

        self.dark = False
        self.items = []
        self.selected = []
        self.tool = "draw"
        self.color = None
        self.sizes = {tool: default for tool, (_lo, _hi, default) in TOOL_SIZES.items()}
        self.undo_stack = []
        self.redo_stack = []
        self.modified = False

        self._cache = None
        self._exclude = ()
        self._live = None
        self._pending = None
        self._drag = None
        self._marquee = None
        self._mouse = None
        self._clipboard = []
        self._text_box = None
        self._editing = None

    @property
    def background_color(self):
        return QColor(DARK_BG if self.dark else LIGHT_BG)

    @property
    def has_drawn(self):
        return bool(self.items)

    def _snapshot(self):
        return [item.clone() for item in self.items]

    def _push_undo(self, snapshot=None):
        self.undo_stack.append(snapshot if snapshot is not None else self._snapshot())
        if len(self.undo_stack) > self.MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _commit_pending(self):
        if self._pending is not None:
            self._push_undo(self._pending)
            self._pending = None

    def _mark_changed(self):
        self.modified = True
        self._cache = None
        self.update()
        self.changed.emit()

    def _restore(self, snapshot):
        self._close_text_box(commit=False)
        self.items = [item.clone() for item in snapshot]
        self._set_selection([])
        self._mark_changed()

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self._snapshot())
        self._restore(self.undo_stack.pop())
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self._snapshot())
        self._restore(self.redo_stack.pop())
        return True

    def reset_history(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.modified = False
        self.changed.emit()

    def set_tool(self, tool):
        if tool not in ("select", "draw", "highlight", "erase", "text"):
            return
        self._close_text_box()
        self.tool = tool
        if tool != "select":
            self._set_selection([])
        self.setCursor(Qt.CrossCursor if tool in ("draw", "highlight") else
                       Qt.IBeamCursor if tool == "text" else Qt.ArrowCursor)
        self.update()
        self.tool_changed.emit(tool)

    def set_mode(self, mode):
        self.set_tool(mode)

    def set_eraser(self):
        self.set_tool("erase")

    def set_color(self, color):
        self.color = None if color is None else QColor(color).name()
        if self.tool == "erase":
            self.set_tool("draw")
        if self.selected:
            self._push_undo()
            for item in self.selected:
                if hasattr(item, "color"):
                    item.color = self.color
                    if isinstance(item, Stroke):
                        item.changed()
            self._mark_changed()
        if self._text_box:
            self._text_box.item.color = self.color
            self._text_box.restyle(self.dark)

    def set_size(self, value, record_undo=True):
        tool = "text" if self.tool == "select" and any(isinstance(i, TextItem) for i in self.selected) else self.tool
        if tool in self.sizes:
            self.sizes[tool] = value
        if self.tool == "select" and self.selected:
            if record_undo:
                self._push_undo()
            for item in self.selected:
                if isinstance(item, Stroke):
                    item.width = value
                    item.changed()
                elif isinstance(item, TextItem):
                    item.size = value
            self._mark_changed()
        if self._text_box:
            self._text_box.item.size = value
            self._text_box.setFont(self._text_box.item.font())
            self._text_box._fit()
        self.update()

    def current_size(self):
        if self.tool == "select":
            for item in self.selected:
                if isinstance(item, TextItem):
                    return round(item.size)
                if isinstance(item, Stroke):
                    return round(item.width)
            return self.sizes["draw"]
        return self.sizes.get(self.tool, 3)

    def set_dark(self, dark):
        if dark == self.dark:
            return
        self.dark = dark
        self._cache = None
        if self._text_box:
            self._text_box.restyle(dark)
        self.update()
        self.appearance_changed.emit()

    def _render(self, painter, exclude=(), dark=None):
        dark = self.dark if dark is None else dark
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        for item in self.items:
            if item is self._editing or item in exclude:
                continue
            item.paint(painter, dark)

    def _cached(self):
        if self._cache is None:
            self._cache = QPixmap(self.size())
            self._cache.fill(self.background_color)
            painter = QPainter(self._cache)
            self._render(painter, self._exclude)
            painter.end()
        return self._cache

    def selection_bounds(self):
        if not self.selected:
            return None
        rect = QRectF(self.selected[0].bounds())
        for item in self.selected[1:]:
            rect = rect.united(item.bounds())
        return rect

    def _handles(self):
        rect = self.selection_bounds()
        if rect is None:
            return {}
        rect = rect.adjusted(-3, -3, 3, 3)
        return {"tl": rect.topLeft(), "tr": rect.topRight(), "bl": rect.bottomLeft(), "br": rect.bottomRight()}

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._cached())
        painter.setRenderHint(QPainter.Antialiasing, True)
        for item in self._exclude:
            item.paint(painter, self.dark)
        if self._live is not None:
            self._live.paint(painter, self.dark)

        highlight = self.palette().color(QPalette.Highlight)
        rect = self.selection_bounds()
        if rect is not None and self.tool == "select":
            painter.setPen(QPen(highlight, 1.5, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect.adjusted(-3, -3, 3, 3))
            painter.setPen(QPen(highlight, 1.5))
            painter.setBrush(QColor("#ffffff"))
            for point in self._handles().values():
                painter.drawRect(QRectF(point.x() - HANDLE / 2, point.y() - HANDLE / 2, HANDLE, HANDLE))
        if self._marquee is not None:
            fill = QColor(highlight)
            fill.setAlpha(40)
            painter.setPen(QPen(highlight, 1, Qt.DashLine))
            painter.setBrush(fill)
            painter.drawRect(self._marquee)
        if self.tool == "erase" and self._mouse is not None:
            radius = self.sizes["erase"] / 2
            painter.setPen(QPen(QColor(128, 128, 128), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(self._mouse, radius, radius)
        painter.end()

    def item_at(self, x, y):
        for item in reversed(self.items):
            if item is not self._editing and item.hit(x, y):
                return item
        return None

    def _handle_at(self, pos):
        for name, point in self._handles().items():
            if abs(pos.x() - point.x()) <= HANDLE and abs(pos.y() - point.y()) <= HANDLE:
                return name
        return None

    def _set_selection(self, items):
        if list(items) != self.selected:
            self.selected = list(items)
            self.update()
            self.selection_changed.emit()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self.setFocus()
        pos = event.position()
        if self._text_box is not None:
            self._close_text_box()
            if self.tool != "text":
                return
        self._pending = self._snapshot()

        if self.tool == "select":
            handle = self._handle_at(pos)
            if handle:
                rect = self.selection_bounds().adjusted(-3, -3, 3, 3)
                anchor = {"tl": rect.bottomRight(), "tr": rect.bottomLeft(),
                          "bl": rect.topRight(), "br": rect.topLeft()}[handle]
                self._drag = {"kind": "scale", "anchor": anchor, "start": rect,
                              "originals": [i.clone() for i in self.selected]}
                return
            item = self.item_at(pos.x(), pos.y())
            shift = bool(event.modifiers() & Qt.ShiftModifier)
            if item is not None:
                if shift:
                    self._set_selection([i for i in self.selected if i is not item] if item in self.selected
                                        else self.selected + [item])
                elif item not in self.selected:
                    self._set_selection([item])
                self._drag = {"kind": "move", "last": pos, "moved": False}
                return
            self._drag = {"kind": "marquee", "origin": pos, "base": list(self.selected) if shift else []}
            if not shift:
                self._set_selection([])
            return

        if self.tool in ("draw", "highlight"):
            color = self.color
            if self.tool == "highlight" and color is None:
                color = HIGHLIGHT_DEFAULT
            self._live = Stroke([(pos.x(), pos.y())], color, self.sizes[self.tool], self.tool == "highlight")
            self.update()
        elif self.tool == "erase":
            self._erase_segment(pos, pos)
            self._drag = {"kind": "erase", "last": pos}
        elif self.tool == "text":
            item = self.item_at(pos.x(), pos.y())
            if isinstance(item, TextItem):
                self._open_text_box(item)
            else:
                self._open_text_box(None, pos)

    def mouseDoubleClickEvent(self, event):
        pos = event.position()
        item = self.item_at(pos.x(), pos.y())
        if isinstance(item, TextItem) and self.tool in ("select", "text"):
            self._drag = None
            self._open_text_box(item)
        else:
            super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position()
        self._mouse = pos
        drag = self._drag

        if self._live is not None and event.buttons() & Qt.LeftButton:
            if self._live.add_point(pos.x(), pos.y()):
                self.update()
            return
        if drag is None:
            if self.tool == "select":
                handle = self._handle_at(pos)
                if handle:
                    self.setCursor(Qt.SizeFDiagCursor if handle in ("tl", "br") else Qt.SizeBDiagCursor)
                elif self.item_at(pos.x(), pos.y()) is not None:
                    self.setCursor(Qt.SizeAllCursor)
                else:
                    self.setCursor(Qt.ArrowCursor)
            elif self.tool == "erase":
                self.update()
            return

        if drag["kind"] == "marquee":
            rect = QRectF(drag["origin"], pos).normalized()
            self._marquee = rect
            picked = [i for i in self.items if i.in_rect(rect)]
            self._set_selection(drag["base"] + [i for i in picked if i not in drag["base"]])
            self.update()
        elif drag["kind"] == "move":
            dx, dy = pos.x() - drag["last"].x(), pos.y() - drag["last"].y()
            if not drag["moved"]:
                drag["moved"] = True
                self._commit_pending()
                self._exclude = tuple(self.selected)
                self._cache = None
            for item in self.selected:
                item.transform(lambda x, y: (x + dx, y + dy), 1.0)
            drag["last"] = pos
            self.update()
        elif drag["kind"] == "scale":
            self._scale_selection(drag, pos)
        elif drag["kind"] == "erase":
            self._erase_segment(drag["last"], pos)
            drag["last"] = pos

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self._live is not None:
            self._commit_pending()
            self.items.append(self._live)
            self._live = None
            self._mark_changed()
        drag, self._drag = self._drag, None
        if drag and drag["kind"] in ("move", "scale") and self._exclude:
            self._exclude = ()
            self._mark_changed()
        if drag and drag["kind"] == "erase" and self._pending is None:
            self._mark_changed()
        self._marquee = None
        self._pending = None
        self.update()

    def leaveEvent(self, event):
        self._mouse = None
        self.update()

    def _scale_selection(self, drag, pos):
        anchor, start = drag["anchor"], drag["start"]
        if not self._exclude:
            self._commit_pending()
            self._exclude = tuple(self.selected)
            self._cache = None
        sx = abs(pos.x() - anchor.x()) / max(1.0, start.width())
        sy = abs(pos.y() - anchor.y()) / max(1.0, start.height())
        scale = max(0.1, max(sx, sy))
        ax, ay = anchor.x(), anchor.y()
        for item, original in zip(self.selected, drag["originals"]):
            fresh = original.clone()
            fresh.transform(lambda x, y: (ax + (x - ax) * scale, ay + (y - ay) * scale), scale)
            item.__dict__.update(fresh.__dict__)
        self.update()

    def _erase_segment(self, a, b):
        radius = self.sizes["erase"] / 2
        steps = max(1, int(math.hypot(b.x() - a.x(), b.y() - a.y()) // max(1.0, radius / 2)))
        centers = [(a.x() + (b.x() - a.x()) * i / steps, a.y() + (b.y() - a.y()) * i / steps) for i in range(steps + 1)]
        area = QRectF(min(a.x(), b.x()) - radius, min(a.y(), b.y()) - radius,
                      abs(b.x() - a.x()) + 2 * radius, abs(b.y() - a.y()) + 2 * radius)
        result, touched = [], False
        for item in self.items:
            if not isinstance(item, Stroke) or not item.bounds().intersects(area):
                result.append(item)
                continue
            reach = (radius + item.width / 3) ** 2
            runs, run = [], []
            for px, py in item.points:
                if any((px - cx) ** 2 + (py - cy) ** 2 <= reach for cx, cy in centers):
                    if run:
                        runs.append(run)
                    run = []
                else:
                    run.append((px, py))
            if run:
                runs.append(run)
            if len(runs) == 1 and len(runs[0]) == len(item.points):
                result.append(item)
                continue
            touched = True
            result.extend(Stroke(r, item.color, item.width, item.highlight) for r in runs if len(r) > 1)
        if touched:
            self._commit_pending()
            self.items = result
            self._mark_changed()

    def _open_text_box(self, item, pos=None):
        self._close_text_box()
        if item is None:
            item = TextItem(pos.x(), pos.y() - self.sizes["text"] * 0.6, "", self.color, self.sizes["text"])
            self._editing = None
        else:
            self._editing = item
            self._set_selection([])
        self._original_text = item.text
        self._cache = None
        box = _TextBox(self, item)
        box.done.connect(self._close_text_box)
        self._text_box = box
        box.show()
        box.setFocus()
        cursor = box.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        box.setTextCursor(cursor)
        self.update()

    def _close_text_box(self, commit=True):
        box = self._text_box
        if box is None:
            return
        self._text_box = None
        item, editing = box.item, self._editing
        self._editing = None
        text = box.toPlainText().rstrip()
        had_focus = box.hasFocus()
        box.finish()
        box.hide()
        box.setParent(None)
        box.deleteLater()
        if had_focus:
            self.setFocus()
        if commit:
            if editing is not None:
                if text != self._original_text or not text:
                    self._push_undo([i.clone() if i is not editing else self._editing_original(i) for i in self.items])
                    if text:
                        editing.text = text
                    else:
                        self.items.remove(editing)
                    self._mark_changed()
            elif text:
                self._push_undo()
                item.text = text
                self.items.append(item)
                self._mark_changed()
        self._cache = None
        self.update()

    def _editing_original(self, item):
        original = item.clone()
        original.text = self._original_text
        return original

    def add_image(self, filepath):
        pixmap = QPixmap(filepath)
        if pixmap.isNull():
            return False
        max_size = 200
        if pixmap.width() > max_size or pixmap.height() > max_size:
            pixmap = pixmap.scaled(max_size, max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.canvas_width - pixmap.width()) / 2
        y = (self.canvas_height - pixmap.height()) / 2
        self._push_undo()
        item = ImageItem(pixmap, QRectF(x, y, pixmap.width(), pixmap.height()))
        self.items.append(item)
        self.set_tool("select")
        self._set_selection([item])
        self._mark_changed()
        return True

    def delete_selection(self):
        if not self.selected:
            return False
        self._push_undo()
        self.items = [i for i in self.items if i not in self.selected]
        self._set_selection([])
        self._mark_changed()
        return True

    delete_selected_image = delete_selection

    def _reorder(self, how):
        if not self.selected:
            return False
        chosen = [i for i in self.items if i in self.selected]
        rest = [i for i in self.items if i not in self.selected]
        if how == "front":
            new = rest + chosen
        elif how == "back":
            new = chosen + rest
        else:
            new = list(self.items)
            indexes = range(len(new) - 2, -1, -1) if how == "forward" else range(1, len(new))
            for i in indexes:
                j = i + 1 if how == "forward" else i - 1
                if new[i] in self.selected and new[j] not in self.selected:
                    new[i], new[j] = new[j], new[i]
        if new == self.items:
            return False
        self._push_undo()
        self.items = new
        self._mark_changed()
        return True

    def bring_to_front(self):
        return self._reorder("front")

    def send_to_back(self):
        return self._reorder("back")

    def bring_forward(self):
        return self._reorder("forward")

    def send_backward(self):
        return self._reorder("backward")

    def _add_copies(self, sources, offset):
        copies = []
        for item in sources:
            copy = item.clone()
            copy.transform(lambda x, y: (x + offset, y + offset), 1.0)
            copies.append(copy)
        self._push_undo()
        self.items.extend(copies)
        if self.tool != "select":
            self.set_tool("select")
        self._set_selection(copies)
        self._mark_changed()

    def duplicate_selection(self):
        if self.selected:
            self._add_copies(self.selected, 12)

    def copy_selection(self):
        self._clipboard = [i.clone() for i in self.selected]

    def cut_selection(self):
        self.copy_selection()
        self.delete_selection()

    def paste(self):
        if self._clipboard:
            self._add_copies(self._clipboard, 12)
            self._clipboard = [i.clone() for i in self.selected]

    def select_all(self):
        self.set_tool("select")
        self._set_selection(list(self.items))

    def nudge(self, dx, dy):
        if not self.selected:
            return
        self._push_undo()
        for item in self.selected:
            item.transform(lambda x, y: (x + dx, y + dy), 1.0)
        self._mark_changed()

    _OVERRIDE_KEYS = {Qt.Key_Delete, Qt.Key_Backspace, Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down,
                      Qt.Key_Escape, Qt.Key_V, Qt.Key_P, Qt.Key_H, Qt.Key_E, Qt.Key_T}
    _CTRL_KEYS = {Qt.Key_A, Qt.Key_C, Qt.Key_X, Qt.Key_V, Qt.Key_D}

    def event(self, event):
        if event.type() == QEvent.ShortcutOverride:
            ctrl = event.modifiers() & Qt.ControlModifier
            if (ctrl and event.key() in self._CTRL_KEYS) or (
                    not ctrl and not event.modifiers() & Qt.AltModifier and event.key() in self._OVERRIDE_KEYS):
                event.accept()
                return True
        return super().event(event)

    def keyPressEvent(self, event):
        key, mods = event.key(), event.modifiers()
        if mods & Qt.ControlModifier:
            actions = {Qt.Key_A: self.select_all, Qt.Key_C: self.copy_selection, Qt.Key_X: self.cut_selection,
                       Qt.Key_V: self.paste, Qt.Key_D: self.duplicate_selection}
            if key in actions:
                actions[key]()
                return
        elif key in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selection()
            return
        elif key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            step = 10 if mods & Qt.ShiftModifier else 1
            dx = {Qt.Key_Left: -step, Qt.Key_Right: step}.get(key, 0)
            dy = {Qt.Key_Up: -step, Qt.Key_Down: step}.get(key, 0)
            self.nudge(dx, dy)
            return
        elif key == Qt.Key_Escape:
            self._set_selection([])
            return
        elif not mods & Qt.AltModifier:
            tools = {Qt.Key_V: "select", Qt.Key_P: "draw", Qt.Key_H: "highlight", Qt.Key_E: "erase", Qt.Key_T: "text"}
            if key in tools:
                self.set_tool(tools[key])
                return
        super().keyPressEvent(event)

    def clear_canvas(self, undoable=False):
        self._close_text_box(commit=False)
        if undoable and self.items:
            self._push_undo()
        self.items = []
        self._set_selection([])
        self._cache = None
        self.update()
        if undoable:
            self._mark_changed()
        else:
            self.reset_history()

    def render_image(self, dark=False):
        image = QImage(self.canvas_width, self.canvas_height, QImage.Format_ARGB32)
        image.fill(QColor(LIGHT_BG if not dark else DARK_BG))
        painter = QPainter(image)
        self._render(painter, dark=dark)
        painter.end()
        return image

    def save_image(self, filepath):
        self._close_text_box()
        image = self.render_image(dark=False)
        image.setText(METADATA_KEY, json.dumps({"v": 1, "items": [i.to_json() for i in self.items]},
                                               separators=(",", ":")))
        return image.save(filepath)

    def load_image(self, filepath):
        image = QImage(filepath)
        if image.isNull():
            return False
        self._close_text_box(commit=False)
        data = image.text(METADATA_KEY)
        items = None
        if data:
            try:
                items = [ITEM_TYPES[d["t"]].from_json(d) for d in json.loads(data)["items"]]
            except (ValueError, KeyError, TypeError):
                items = None
        if items is None:
            pixmap = QPixmap.fromImage(image.convertToFormat(QImage.Format_ARGB32))
            pixmap.setMask(QBitmap.fromImage(image.createMaskFromColor(QColor(Qt.white).rgb(), Qt.MaskInColor)))
            items = [ImageItem(pixmap, QRectF(0, 0, image.width(), image.height()), ink_raster=True)]
        self.items = items
        self._set_selection([])
        self._cache = None
        self.update()
        return True


ICON_FILES = {
    "select": "mouse-pointer-2", "draw": "pencil", "highlight": "highlighter", "erase": "eraser", "text": "type",
    "image": "image-plus", "undo": "undo-2", "redo": "redo-2", "trash": "trash-2", "front": "bring-to-front",
    "forward": "arrow-up", "backward": "arrow-down", "back": "send-to-back", "duplicate": "copy", "delete": "trash-2",
}


PAD_STYLE = """
QToolButton { border: 1px solid transparent; border-radius: 7px; padding: 3px; }
QToolButton:hover { background: palette(button); border: 1px solid palette(mid); }
QToolButton:checked { background: palette(highlight); border: 1px solid palette(highlight); }
QToolButton:disabled { background: transparent; }
QFrame#drawToolbar, QFrame#canvasFrame { border: 1px solid palette(mid); border-radius: 9px; }
QLabel#toolHint { color: gray; font-size: 11px; }
"""

TOOLS = [
    ("select", "Select", "Select and move things (V)  ·  Ctrl+Shift+A"),
    ("draw", "Pen", "Pen (P)  ·  Ctrl+Shift+D"),
    ("highlight", "Highlighter", "Highlighter (H)  ·  Ctrl+Shift+H"),
    ("erase", "Eraser", "Eraser (E)  ·  Ctrl+Shift+E"),
    ("text", "Text", "Text (T)  ·  Ctrl+Shift+X"),
]


class DrawingPad(QWidget):
    def __init__(self):
        super().__init__()
        self.recent_colors = []
        self.max_recent_colors = 3
        self.tool_buttons = {}
        self.icon_buttons = {}
        self.swatch_buttons = []
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(PAD_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 8)
        layout.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel("Drawing Pad")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(title)
        header.addStretch()
        self.autosave = edit_operations.AutosaveToggle("drawing")
        header.addWidget(self.autosave)
        layout.addLayout(header)

        self.canvas = DrawingCanvas()

        toolbar = QFrame()
        toolbar.setObjectName("drawToolbar")
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(5, 4, 5, 4)
        bar.setSpacing(3)
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        for tool, name, tip in TOOLS:
            btn = self._icon_button(tool, name, tip, checkable=True)
            btn.clicked.connect(lambda _=False, t=tool: self.set_mode(t))
            self.tool_group.addButton(btn)
            self.tool_buttons[tool] = btn
            bar.addWidget(btn)
        bar.addWidget(self._divider())
        image_btn = self._icon_button("image", "Add image", "Add an image  ·  Ctrl+Shift+U")
        image_btn.clicked.connect(self.upload_image)
        bar.addWidget(image_btn)
        bar.addWidget(self._divider())
        self.undo_btn = self._icon_button("undo", "Undo", "Undo  ·  Ctrl+Z (click the pad first)")
        self.undo_btn.clicked.connect(self.canvas.undo)
        self.redo_btn = self._icon_button("redo", "Redo", "Redo  ·  Ctrl+Y")
        self.redo_btn.clicked.connect(self.canvas.redo)
        bar.addWidget(self.undo_btn)
        bar.addWidget(self.redo_btn)
        bar.addStretch()
        clear_btn = self._icon_button("trash", "Clear all", "Clear the whole pad (Ctrl+Z brings it back)")
        clear_btn.clicked.connect(self.clear_all)
        bar.addWidget(clear_btn)
        layout.addWidget(toolbar)

        style_row = QHBoxLayout()
        style_row.setSpacing(5)
        for color in SWATCHES:
            style_row.addWidget(self._swatch(color))
        more = QToolButton()
        more.setIconSize(QSize(16, 16))
        more.setProperty("icon_name", "plus")
        self.icon_buttons["more"] = more
        more.setFixedSize(QSize(24, 24))
        more.setToolTip("More colors...  ·  Ctrl+Shift+C")
        more.setAccessibleName("More colors")
        more.clicked.connect(self.pick_color)
        style_row.addWidget(more)
        self.recent_colors_layout = QHBoxLayout()
        self.recent_colors_layout.setSpacing(5)
        style_row.addLayout(self.recent_colors_layout)
        style_row.addStretch()
        size_label = QLabel("Size")
        style_row.addWidget(size_label)
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setFixedWidth(96)
        self.size_slider.setAccessibleName("Pen, eraser or text size")
        self.size_slider.valueChanged.connect(self._size_changed)
        self.size_slider.sliderPressed.connect(self._size_drag_started)
        style_row.addWidget(self.size_slider)
        self.size_preview = QLabel()
        self.size_preview.setFixedSize(30, 30)
        self.size_preview.setAlignment(Qt.AlignCenter)
        style_row.addWidget(self.size_preview)
        layout.addLayout(style_row)

        frame = QFrame()
        frame.setObjectName("canvasFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(2, 2, 2, 2)
        frame_layout.addWidget(self.canvas)
        layout.addWidget(frame, alignment=Qt.AlignHCenter)

        arrange_bar = QFrame()
        arrange_bar.setObjectName("drawToolbar")
        arrange = QHBoxLayout(arrange_bar)
        arrange.setContentsMargins(8, 3, 5, 3)
        arrange.setSpacing(3)
        self.selection_label = QLabel("Selection")
        self.selection_label.setObjectName("toolHint")
        arrange.addWidget(self.selection_label)
        arrange.addStretch()
        self.arrange_buttons = []
        for kind, name, tip, slot in (
                ("front", "Bring to front", "Bring to front  ·  Ctrl+Shift+]", self.bring_to_front),
                ("forward", "Bring forward", "Bring forward  ·  Ctrl+]", self.bring_forward),
                ("backward", "Send backward", "Send backward  ·  Ctrl+[", self.send_backward),
                ("back", "Send to back", "Send to back  ·  Ctrl+Shift+[", self.send_to_back),
                ("duplicate", "Duplicate", "Duplicate  ·  Ctrl+D (click the pad first)", self.canvas.duplicate_selection),
                ("delete", "Delete", "Delete  ·  Delete key or Ctrl+Shift+Del", self.delete_image)):
            btn = self._icon_button(kind, name, tip)
            btn.setFixedSize(QSize(32, 32))
            btn.setIconSize(QSize(20, 20))
            btn.clicked.connect(slot)
            arrange.addWidget(btn)
            self.arrange_buttons.append(btn)
        layout.addWidget(arrange_bar)

        self.hint = QLabel()
        self.hint.setObjectName("toolHint")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        layout.addStretch()

        self.canvas.tool_changed.connect(self._tool_changed)
        self.canvas.appearance_changed.connect(self._update_preview)
        self.canvas.selection_changed.connect(self._selection_changed)
        self.canvas.changed.connect(self._history_changed)
        self.canvas.changed.connect(self._selection_changed)
        self._refresh_icons()
        self._tool_changed(self.canvas.tool)
        self._selection_changed()
        self._history_changed()
        self._mark_swatch(None)

    def _icon_button(self, kind, name, tip, checkable=False):
        btn = QToolButton()
        btn.setCheckable(checkable)
        btn.setIconSize(QSize(24, 24))
        btn.setFixedSize(QSize(36, 36))
        btn.setToolTip(tip)
        btn.setAccessibleName(name)
        btn.setProperty("icon_kind", kind)
        self.icon_buttons[kind] = btn
        return btn

    def _divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFixedHeight(24)
        line.setStyleSheet("color: palette(mid);")
        return line

    def _refresh_icons(self):
        palette = self.palette()
        for kind, btn in self.icon_buttons.items():
            btn.setIcon(edit_operations.svg_icon(btn.property("icon_name") or ICON_FILES[kind], palette))
        self._update_preview()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange:
            self._refresh_icons()
            self._restyle_swatches()

    def _swatch(self, color):
        btn = QToolButton()
        btn.setCheckable(True)
        btn.setFixedSize(QSize(24, 24))
        btn.setProperty("swatch", color)
        btn.setToolTip("Ink (black, or white in dark mode)" if color is None else QColor(color).name())
        btn.setAccessibleName("Ink color" if color is None else f"Color {QColor(color).name()}")
        btn.clicked.connect(lambda _=False, c=color: self.select_color(c))
        self.swatch_buttons.append(btn)
        self._style_swatch(btn)
        return btn

    def _style_swatch(self, btn):
        color = btn.property("swatch")
        fill = "palette(text)" if color is None else QColor(color).name()
        btn.setStyleSheet(
            f"QToolButton {{ background: {fill}; border: 2px solid palette(mid); border-radius: 12px; }}"
            f"QToolButton:checked {{ border: 3px solid palette(highlight); }}"
            f"QToolButton:hover {{ border: 2px solid palette(highlight); }}")

    def _restyle_swatches(self):
        for btn in self.swatch_buttons:
            if btn:
                self._style_swatch(btn)

    def _mark_swatch(self, color):
        name = None if color is None else QColor(color).name()
        for btn in self.swatch_buttons:
            value = btn.property("swatch")
            btn.setChecked((value is None and name is None) or (value is not None and QColor(value).name() == name))

    def select_color(self, color):
        self.canvas.set_color(color)
        self._mark_swatch(color)
        self._update_preview()

    def select_recent_color(self, color):
        self.select_color(color)

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.canvas.color or "#000000"), self, "Pick a color")
        if color.isValid():
            self.add_recent_color(color)
            self.select_color(color.name())

    def add_recent_color(self, color):
        name = QColor(color).name()
        if name in [c for c in SWATCHES if c] or name in self.recent_colors:
            return
        self.recent_colors.insert(0, name)
        del self.recent_colors[self.max_recent_colors:]
        self.update_recent_colors_ui()

    def update_recent_colors_ui(self):
        self.swatch_buttons = [b for b in self.swatch_buttons if b.property("swatch") not in self._shown_recent()]
        while self.recent_colors_layout.count():
            item = self.recent_colors_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        for color in self.recent_colors:
            self.recent_colors_layout.addWidget(self._swatch(color))
        self._mark_swatch(self.canvas.color)

    def _shown_recent(self):
        shown = set()
        for i in range(self.recent_colors_layout.count()):
            widget = self.recent_colors_layout.itemAt(i).widget()
            if widget is not None:
                shown.add(widget.property("swatch"))
        return shown

    def _size_drag_started(self):
        if self.canvas.tool == "select" and self.canvas.selected:
            self.canvas._push_undo()
            self._size_undo_done = True

    def _size_changed(self, value):
        record = not getattr(self, "_size_undo_done", False) and not self.size_slider.isSliderDown()
        self.canvas.set_size(value, record_undo=record)
        if not self.size_slider.isSliderDown():
            self._size_undo_done = False
        self._update_preview()

    def _sync_slider(self):
        tool = self.canvas.tool
        if tool == "select":
            tool = "text" if any(isinstance(i, TextItem) for i in self.canvas.selected) else "draw"
        lo, hi, _default = TOOL_SIZES[tool]
        self.size_slider.blockSignals(True)
        self.size_slider.setRange(lo, hi)
        self.size_slider.setValue(max(lo, min(hi, self.canvas.current_size())))
        self.size_slider.blockSignals(False)
        self.size_slider.setEnabled(self.canvas.tool != "select" or bool(self.canvas.selected))
        self._update_preview()

    def _update_preview(self):
        size = self.size_slider.value() if self.size_slider.isEnabled() else 3
        tool = self.canvas.tool
        pm = QPixmap(60, 60)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        color = _ink(self.canvas.color, self.canvas.dark)
        if tool == "highlight" and self.canvas.color is None:
            color = QColor(HIGHLIGHT_DEFAULT)
        if tool == "highlight":
            color.setAlpha(150)
        if tool == "text":
            font = QFont("Arial")
            font.setPixelSize(max(12, min(52, size * 2)))
            p.setFont(font)
            p.setPen(color)
            p.drawText(QRectF(0, 0, 60, 60), Qt.AlignCenter, "Aa")
        elif tool == "erase":
            p.setPen(QPen(self.palette().color(QPalette.Text), 2))
            radius = max(2, min(28, size / 2 * 2))
            p.drawEllipse(QPointF(30, 30), radius, radius)
        else:
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            radius = max(2, min(28, size))
            p.drawEllipse(QPointF(30, 30), radius, radius)
        p.end()
        pm.setDevicePixelRatio(2)
        self.size_preview.setPixmap(pm)

    def _tool_changed(self, tool):
        btn = self.tool_buttons.get(tool)
        if btn and not btn.isChecked():
            btn.setChecked(True)
        self.hint.setText(TOOL_HINTS.get(tool, ""))
        self._sync_slider()

    def _selection_changed(self):
        has = bool(self.canvas.selected)
        for btn in self.arrange_buttons:
            btn.setEnabled(has)
        count = len(self.canvas.selected)
        self.selection_label.setText(f"{count} selected" if count else "Nothing selected")
        if has:
            colors = {getattr(i, "color", "none") for i in self.canvas.selected} - {"none"}
            if len(colors) == 1:
                self._mark_swatch(colors.pop())
        self._sync_slider()

    def _history_changed(self):
        self.undo_btn.setEnabled(bool(self.canvas.undo_stack))
        self.redo_btn.setEnabled(bool(self.canvas.redo_stack))

    def upload_image(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Add Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All Files (*)")
        if filepath and not self.canvas.add_image(filepath):
            QMessageBox.warning(self, "Couldn't Add Image", "That file couldn't be opened as an image.")

    def delete_image(self):
        self.canvas.delete_selection()

    def clear_all(self):
        if not self.canvas.items:
            return
        reply = QMessageBox.question(
            self, "Clear All", "Clear everything on the drawing pad?\n\nYou can bring it back with Ctrl+Z.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.canvas.clear_canvas(undoable=True)

    def bring_to_front(self):
        self.canvas.bring_to_front()

    def send_to_back(self):
        self.canvas.send_to_back()

    def bring_forward(self):
        self.canvas.bring_forward()

    def send_backward(self):
        self.canvas.send_backward()

    def set_mode(self, mode):
        self.canvas.set_tool(mode)

    def has_drawing(self):
        return self.canvas.has_drawn

    def save_drawing(self, filepath):
        ok = self.canvas.save_image(filepath)
        if ok:
            self.canvas.modified = False
            self.canvas.changed.emit()
        return ok

    def load_drawing(self, filepath):
        ok = self.canvas.load_image(filepath)
        self.canvas.reset_history()
        return ok


def create_drawing_pad():
    return DrawingPad()
