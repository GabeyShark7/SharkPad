from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QSlider, QToolButton, QVBoxLayout, QWidget,
)

from sharkpad.drawing.canvas import TOOL_SIZES, DrawingCanvas
from sharkpad.drawing.color_picker import ColorPicker
from sharkpad.drawing.items import HIGHLIGHT_DEFAULT, ink
from sharkpad.editor.autosave_toggle import AutosaveToggle
from sharkpad.icons import svg_icon

PAD_STYLE = """
QToolButton { border: 1px solid transparent; border-radius: 7px; padding: 3px; }
QToolButton:hover { background: palette(button); border: 1px solid palette(mid); }
QToolButton:checked { background: palette(highlight); border: 1px solid palette(highlight); }
QToolButton:disabled { background: transparent; }
QFrame#drawToolbar, QFrame#canvasFrame { border: 1px solid palette(mid); border-radius: 9px; }
QLabel#toolHint { color: gray; font-size: 11px; }
"""

TOOL_BUTTONS = [
    ("select", "mouse-pointer-2", "Select", "Select and move things (V)  ·  Ctrl+Shift+A"),
    ("draw", "pencil", "Pen", "Pen (P)  ·  Ctrl+Shift+D"),
    ("highlight", "highlighter", "Highlighter", "Highlighter (H)  ·  Ctrl+Shift+H"),
    ("erase", "eraser", "Eraser", "Eraser (E)  ·  Ctrl+Shift+E"),
    ("text", "type", "Text", "Text (T)  ·  Ctrl+Shift+X"),
]

TOOL_HINTS = {
    "select": "Drag a box to select · Shift+click adds · Drag corners to resize · Delete removes",
    "draw": "Draw with your mouse or pen",
    "highlight": "Highlight over your drawing",
    "erase": "Rub over lines to erase them",
    "text": "Click to type · Click away or press Esc when done · Double-click text to edit it",
}


class DrawingPad(QWidget):
    def __init__(self):
        super().__init__()
        self.canvas = DrawingCanvas()
        self.tool_buttons = {}
        self.icon_buttons = []
        self.arrange_buttons = []
        self._size_undo_done = False

        self.setStyleSheet(PAD_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 8)
        layout.setSpacing(7)
        layout.addLayout(self._build_header())
        layout.addWidget(self._build_toolbar())
        layout.addLayout(self._build_style_row())

        frame = QFrame()
        frame.setObjectName("canvasFrame")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(2, 2, 2, 2)
        frame_layout.addWidget(self.canvas)
        layout.addWidget(frame, alignment=Qt.AlignHCenter)

        layout.addWidget(self._build_arrange_bar())
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

    def _build_header(self):
        header = QHBoxLayout()
        title = QLabel("Drawing Pad")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header.addWidget(title)
        header.addStretch()
        self.autosave = AutosaveToggle("drawing")
        header.addWidget(self.autosave)
        return header

    def _build_toolbar(self):
        toolbar = QFrame()
        toolbar.setObjectName("drawToolbar")
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(5, 4, 5, 4)
        bar.setSpacing(3)
        self.tool_group = QButtonGroup(self)
        for tool, icon, name, tip in TOOL_BUTTONS:
            btn = self._icon_button(icon, name, tip, checkable=True)
            btn.clicked.connect(lambda _=False, t=tool: self.canvas.set_tool(t))
            self.tool_group.addButton(btn)
            self.tool_buttons[tool] = btn
            bar.addWidget(btn)
        bar.addWidget(self._divider())
        image_btn = self._icon_button("image-plus", "Add image", "Add an image  ·  Ctrl+Shift+U")
        image_btn.clicked.connect(self.upload_image)
        bar.addWidget(image_btn)
        bar.addWidget(self._divider())
        self.undo_btn = self._icon_button("undo-2", "Undo", "Undo  ·  Ctrl+Z (click the pad first)")
        self.undo_btn.clicked.connect(self.canvas.undo)
        self.redo_btn = self._icon_button("redo-2", "Redo", "Redo  ·  Ctrl+Y")
        self.redo_btn.clicked.connect(self.canvas.redo)
        bar.addWidget(self.undo_btn)
        bar.addWidget(self.redo_btn)
        bar.addStretch()
        clear_btn = self._icon_button("trash-2", "Clear all", "Clear the whole pad (Ctrl+Z brings it back)")
        clear_btn.clicked.connect(self.clear_all)
        bar.addWidget(clear_btn)
        return toolbar

    def _build_style_row(self):
        row = QHBoxLayout()
        row.setSpacing(5)
        self.colors = ColorPicker(self.canvas)
        self.colors.color_chosen.connect(self._update_preview)
        row.addWidget(self.colors)
        row.addStretch()
        row.addWidget(QLabel("Size"))
        self.size_slider = QSlider(Qt.Horizontal)
        self.size_slider.setFixedWidth(96)
        self.size_slider.setAccessibleName("Pen, eraser or text size")
        self.size_slider.valueChanged.connect(self._size_changed)
        self.size_slider.sliderPressed.connect(self._size_drag_started)
        row.addWidget(self.size_slider)
        self.size_preview = QLabel()
        self.size_preview.setFixedSize(30, 30)
        self.size_preview.setAlignment(Qt.AlignCenter)
        row.addWidget(self.size_preview)
        return row

    def _build_arrange_bar(self):
        arrange_bar = QFrame()
        arrange_bar.setObjectName("drawToolbar")
        arrange = QHBoxLayout(arrange_bar)
        arrange.setContentsMargins(8, 3, 5, 3)
        arrange.setSpacing(3)
        self.selection_label = QLabel("Selection")
        self.selection_label.setObjectName("toolHint")
        arrange.addWidget(self.selection_label)
        arrange.addStretch()
        canvas = self.canvas
        for icon, name, tip, slot in (
                ("bring-to-front", "Bring to front", "Bring to front  ·  Ctrl+Shift+]", canvas.bring_to_front),
                ("arrow-up", "Bring forward", "Bring forward  ·  Ctrl+]", canvas.bring_forward),
                ("arrow-down", "Send backward", "Send backward  ·  Ctrl+[", canvas.send_backward),
                ("send-to-back", "Send to back", "Send to back  ·  Ctrl+Shift+[", canvas.send_to_back),
                ("copy", "Duplicate", "Duplicate  ·  Ctrl+D (click the pad first)", canvas.duplicate_selection),
                ("trash-2", "Delete", "Delete  ·  Delete key or Ctrl+Shift+Del", canvas.delete_selection)):
            btn = self._icon_button(icon, name, tip)
            btn.setFixedSize(QSize(32, 32))
            btn.setIconSize(QSize(20, 20))
            btn.clicked.connect(slot)
            arrange.addWidget(btn)
            self.arrange_buttons.append(btn)
        return arrange_bar

    def _icon_button(self, icon, name, tip, checkable=False):
        btn = QToolButton()
        btn.setCheckable(checkable)
        btn.setIconSize(QSize(24, 24))
        btn.setFixedSize(QSize(36, 36))
        btn.setToolTip(tip)
        btn.setAccessibleName(name)
        btn.setProperty("icon_name", icon)
        self.icon_buttons.append(btn)
        return btn

    def _divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFixedHeight(24)
        line.setStyleSheet("color: palette(mid);")
        return line

    def _refresh_icons(self):
        for btn in self.icon_buttons:
            btn.setIcon(svg_icon(btn.property("icon_name"), self.palette()))
        self._update_preview()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange:
            self._refresh_icons()

    def _size_drag_started(self):
        if self.canvas.tool == "select" and self.canvas.selected:
            self.canvas._push_undo()
            self._size_undo_done = True

    def _size_changed(self, value):
        record = not self._size_undo_done and not self.size_slider.isSliderDown()
        self.canvas.set_size(value, record_undo=record)
        if not self.size_slider.isSliderDown():
            self._size_undo_done = False
        self._update_preview()

    def _sync_slider(self):
        lo, hi, _default = TOOL_SIZES[self.canvas.size_tool()]
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
        color = ink(self.canvas.color, self.canvas.dark)
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
            radius = max(2, min(28, size))
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
        count = len(self.canvas.selected)
        for btn in self.arrange_buttons:
            btn.setEnabled(count > 0)
        self.selection_label.setText(f"{count} selected" if count else "Nothing selected")
        if count:
            colors = {getattr(i, "color", "none") for i in self.canvas.selected} - {"none"}
            if len(colors) == 1:
                self.colors.mark(colors.pop())
        self._sync_slider()

    def _history_changed(self):
        self.undo_btn.setEnabled(bool(self.canvas.history.undo_stack))
        self.redo_btn.setEnabled(bool(self.canvas.history.redo_stack))

    def upload_image(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Add Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All Files (*)")
        if filepath and not self.canvas.add_image(filepath):
            QMessageBox.warning(self, "Couldn't Add Image", "That file couldn't be opened as an image.")

    def clear_all(self):
        if not self.canvas.items:
            return
        reply = QMessageBox.question(
            self, "Clear All", "Clear everything on the drawing pad?\n\nYou can bring it back with Ctrl+Z.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.canvas.clear_canvas(undoable=True)
