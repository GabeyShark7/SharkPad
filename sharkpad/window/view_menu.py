import sys

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QInputDialog, QPlainTextEdit

from sharkpad.editor.editor_font import DEFAULT_FONT_SIZE, MAX_SIZE, MIN_SIZE
from sharkpad.editor.keyboard_helpers import CtrlWheelZoom


class ViewMenu:
    def __init__(self, win):
        self.win = win
        self.focus_mode = False
        self.pad_before_focus = True
        menu = win.menuBar().addMenu("&View")

        wrap_on = win.setting_bool("word_wrap", True)
        self.set_word_wrap(wrap_on)
        win.add_action(menu, "Word Wrap", self.set_word_wrap, checkable=True, checked=wrap_on)

        numbers_on = win.setting_bool("line_numbers", True)
        win.editor.set_line_numbers(numbers_on)
        win.add_action(menu, "Line Numbers", self.set_line_numbers, checkable=True, checked=numbers_on)
        menu.addSeparator()

        win.add_action(menu, "Zoom In (Ctrl+=)", lambda: self.zoom(2), ["Ctrl+=", "Ctrl++"])
        win.add_action(menu, "Zoom Out (Ctrl+-)", lambda: self.zoom(-2), ["Ctrl+-"])
        win.add_action(menu, "Reset Zoom (Ctrl+0)", lambda: self.set_font_size(DEFAULT_FONT_SIZE), ["Ctrl+0"])
        win.add_action(menu, "Set Font Size...", self.ask_font_size)
        self.size_indicator = QAction("", win)
        self.size_indicator.setDisabled(True)
        menu.addAction(self.size_indicator)
        self._show_size()
        menu.addSeparator()

        win.add_action(menu, "Show Drawing Pad", self.show_drawing_pad,
                       checkable=True, checked=win.drawing_pad.isVisible())
        focus_keys = ["F11", "Ctrl+Meta+F"] if sys.platform == "darwin" else ["F11"]
        self.focus_action = win.add_action(menu, "Focus Mode (F11)", lambda _=False: self.toggle_focus_mode())
        self.focus_action.setCheckable(True)
        win.bind(focus_keys, self.toggle_focus_mode)

        self.wheel_zoom = CtrlWheelZoom(self.zoom, win.editor)
        win.editor.viewport().installEventFilter(self.wheel_zoom)

    def set_word_wrap(self, on):
        self.win.editor.setLineWrapMode(QPlainTextEdit.WidgetWidth if on else QPlainTextEdit.NoWrap)
        self.win.settings.setValue("word_wrap", on)

    def set_line_numbers(self, on):
        self.win.editor.set_line_numbers(on)
        self.win.settings.setValue("line_numbers", on)

    def _show_size(self):
        self.size_indicator.setText(f"Font Size: {self.win.editor_font.size}")

    def set_font_size(self, size):
        self.win.editor_font.set_size(size)
        self._show_size()
        self.win.status_bar.showMessage(f"Text size: {self.win.editor_font.size}", 1500)

    def zoom(self, delta):
        self.set_font_size(self.win.editor_font.size + delta)

    def ask_font_size(self):
        size, ok = QInputDialog.getInt(self.win, "Font Size", "Text size:", self.win.editor_font.size, MIN_SIZE, MAX_SIZE)
        if ok:
            self.set_font_size(size)

    def show_drawing_pad(self, on):
        self.win.drawing_pad.setVisible(on)
        self.win.settings.setValue("drawing_pad_visible", on)

    def toggle_focus_mode(self):
        win = self.win
        if not self.focus_mode:
            self.pad_before_focus = win.drawing_pad.isVisible()
            win.drawing_pad.setVisible(False)
            win.showFullScreen()
            win.status_bar.showMessage("Focus Mode: press F11 or Esc to leave.", 4000)
        else:
            win.drawing_pad.setVisible(self.pad_before_focus)
            win.showNormal()
        self.focus_mode = not self.focus_mode
        self.focus_action.setChecked(self.focus_mode)
