from PySide6.QtCore import QEvent, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from sharkpad.drawing.canvas_actions import CanvasActions
from sharkpad.drawing.drawing_file import load_drawing, paint_items, save_drawing
from sharkpad.drawing.eraser import erase_segment
from sharkpad.drawing.history import History
from sharkpad.drawing.items import DARK_BG, HIGHLIGHT_DEFAULT, LIGHT_BG, Stroke, TextItem
from sharkpad.drawing.text_box import TextBox

PAD_WIDTH = 450
PAD_HEIGHT = 400
HANDLE = 8
TOOLS = ("select", "draw", "highlight", "erase", "text")
TOOL_SIZES = {"draw": (1, 40, 3), "highlight": (6, 48, 18), "erase": (4, 80, 18), "text": (8, 72, 20)}
TOOL_KEYS = {Qt.Key_V: "select", Qt.Key_P: "draw", Qt.Key_H: "highlight", Qt.Key_E: "erase", Qt.Key_T: "text"}
ARROW_KEYS = (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down)
OVERRIDE_KEYS = {Qt.Key_Delete, Qt.Key_Backspace, Qt.Key_Escape, *ARROW_KEYS, *TOOL_KEYS}
CTRL_KEYS = {Qt.Key_A, Qt.Key_C, Qt.Key_X, Qt.Key_V, Qt.Key_D}


class DrawingCanvas(CanvasActions, QWidget):
    changed = Signal()
    selection_changed = Signal()
    tool_changed = Signal(str)
    appearance_changed = Signal()

    def __init__(self):
        super().__init__()
        self.setFixedSize(PAD_WIDTH, PAD_HEIGHT)
        self.setFocusPolicy(Qt.ClickFocus)
        self.setMouseTracking(True)
        self.setAccessibleName("Drawing canvas")

        self.dark = False
        self.items = []
        self.selected = []
        self.tool = "draw"
        self.color = None
        self.sizes = {tool: default for tool, (_lo, _hi, default) in TOOL_SIZES.items()}
        self.history = History()
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
        self._original_text = ""

    def _snapshot(self):
        return [item.clone() for item in self.items]

    def _push_undo(self, snapshot=None):
        self.history.push(snapshot if snapshot is not None else self._snapshot())

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
        snapshot = self.history.undo(self._snapshot())
        if snapshot is None:
            return False
        self._restore(snapshot)
        return True

    def redo(self):
        snapshot = self.history.redo(self._snapshot())
        if snapshot is None:
            return False
        self._restore(snapshot)
        return True

    def reset_history(self):
        self.history.clear()
        self.modified = False
        self.changed.emit()

    def set_tool(self, tool):
        if tool not in TOOLS:
            return
        self._close_text_box()
        self.tool = tool
        if tool != "select":
            self._set_selection([])
        self.setCursor(Qt.CrossCursor if tool in ("draw", "highlight") else
                       Qt.IBeamCursor if tool == "text" else Qt.ArrowCursor)
        self.update()
        self.tool_changed.emit(tool)

    def set_dark(self, dark):
        if dark == self.dark:
            return
        self.dark = dark
        self._cache = None
        if self._text_box:
            self._text_box.restyle(dark)
        self.update()
        self.appearance_changed.emit()

    def _cached(self):
        if self._cache is None:
            self._cache = QPixmap(self.size())
            self._cache.fill(QColor(DARK_BG if self.dark else LIGHT_BG))
            painter = QPainter(self._cache)
            paint_items(painter, self.items, self.dark, skip=(self._editing, *self._exclude))
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
            self._start_select_drag(pos, bool(event.modifiers() & Qt.ShiftModifier))
        elif self.tool in ("draw", "highlight"):
            color = self.color
            if self.tool == "highlight" and color is None:
                color = HIGHLIGHT_DEFAULT
            self._live = Stroke([(pos.x(), pos.y())], color, self.sizes[self.tool], self.tool == "highlight")
            self.update()
        elif self.tool == "erase":
            self._erase(pos, pos)
            self._drag = {"kind": "erase", "last": pos}
        elif self.tool == "text":
            item = self.item_at(pos.x(), pos.y())
            if isinstance(item, TextItem):
                self._open_text_box(item)
            else:
                self._open_text_box(None, pos)

    def _start_select_drag(self, pos, shift):
        handle = self._handle_at(pos)
        if handle:
            rect = self.selection_bounds().adjusted(-3, -3, 3, 3)
            anchor = {"tl": rect.bottomRight(), "tr": rect.bottomLeft(),
                      "bl": rect.topRight(), "br": rect.topLeft()}[handle]
            self._drag = {"kind": "scale", "anchor": anchor, "start": rect,
                          "originals": [i.clone() for i in self.selected]}
            return
        item = self.item_at(pos.x(), pos.y())
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
            self._update_hover(pos)
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
                self._start_live_edit()
            for item in self.selected:
                item.transform(lambda x, y: (x + dx, y + dy), 1.0)
            drag["last"] = pos
            self.update()
        elif drag["kind"] == "scale":
            self._scale_selection(drag, pos)
        elif drag["kind"] == "erase":
            self._erase(drag["last"], pos)
            drag["last"] = pos

    def _update_hover(self, pos):
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

    def _start_live_edit(self):
        self._commit_pending()
        self._exclude = tuple(self.selected)
        self._cache = None

    def _scale_selection(self, drag, pos):
        anchor, start = drag["anchor"], drag["start"]
        if not self._exclude:
            self._start_live_edit()
        sx = abs(pos.x() - anchor.x()) / max(1.0, start.width())
        sy = abs(pos.y() - anchor.y()) / max(1.0, start.height())
        scale = max(0.1, max(sx, sy))
        ax, ay = anchor.x(), anchor.y()
        for item, original in zip(self.selected, drag["originals"]):
            fresh = original.clone()
            fresh.transform(lambda x, y: (ax + (x - ax) * scale, ay + (y - ay) * scale), scale)
            item.__dict__.update(fresh.__dict__)
        self.update()

    def _erase(self, a, b):
        result = erase_segment(self.items, a, b, self.sizes["erase"] / 2)
        if result is not None:
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
        box = TextBox(self, item)
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
                    before = editing.clone()
                    before.text = self._original_text
                    self._push_undo([i.clone() if i is not editing else before for i in self.items])
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

    def event(self, event):
        if event.type() == QEvent.ShortcutOverride:
            ctrl = event.modifiers() & Qt.ControlModifier
            if (ctrl and event.key() in CTRL_KEYS) or (
                    not ctrl and not event.modifiers() & Qt.AltModifier and event.key() in OVERRIDE_KEYS):
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
        elif key in ARROW_KEYS:
            step = 10 if mods & Qt.ShiftModifier else 1
            dx = {Qt.Key_Left: -step, Qt.Key_Right: step}.get(key, 0)
            dy = {Qt.Key_Up: -step, Qt.Key_Down: step}.get(key, 0)
            self.nudge(dx, dy)
            return
        elif key == Qt.Key_Escape:
            self._set_selection([])
            return
        elif not mods & Qt.AltModifier and key in TOOL_KEYS:
            self.set_tool(TOOL_KEYS[key])
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

    def save(self, filepath):
        self._close_text_box()
        ok = save_drawing(self.items, self.width(), self.height(), filepath)
        if ok:
            self.modified = False
            self.changed.emit()
        return ok

    def load(self, filepath):
        items = load_drawing(filepath)
        if items is not None:
            self._close_text_box(commit=False)
            self.items = items
            self._set_selection([])
            self._cache = None
            self.update()
        self.reset_history()
        return items is not None
