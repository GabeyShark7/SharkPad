from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPixmap

from sharkpad.drawing.items import ImageItem, Stroke, TextItem

MAX_IMAGE_SIZE = 200
COPY_OFFSET = 12


class CanvasActions:
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

    def size_tool(self):
        if self.tool == "select":
            return "text" if any(isinstance(i, TextItem) for i in self.selected) else "draw"
        return self.tool

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
            self._text_box.fit()
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

    def add_image(self, filepath):
        pixmap = QPixmap(filepath)
        if pixmap.isNull():
            return False
        if pixmap.width() > MAX_IMAGE_SIZE or pixmap.height() > MAX_IMAGE_SIZE:
            pixmap = pixmap.scaled(MAX_IMAGE_SIZE, MAX_IMAGE_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = (self.width() - pixmap.width()) / 2
        y = (self.height() - pixmap.height()) / 2
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

    def _add_copies(self, sources):
        copies = []
        for item in sources:
            copy = item.clone()
            copy.transform(lambda x, y: (x + COPY_OFFSET, y + COPY_OFFSET), 1.0)
            copies.append(copy)
        self._push_undo()
        self.items.extend(copies)
        if self.tool != "select":
            self.set_tool("select")
        self._set_selection(copies)
        self._mark_changed()

    def duplicate_selection(self):
        if self.selected:
            self._add_copies(self.selected)

    def copy_selection(self):
        self._clipboard = [i.clone() for i in self.selected]

    def cut_selection(self):
        self.copy_selection()
        self.delete_selection()

    def paste(self):
        if self._clipboard:
            self._add_copies(self._clipboard)
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
