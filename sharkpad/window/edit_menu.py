from PySide6.QtWidgets import QApplication

from sharkpad.editor import text_tools
from sharkpad.spelling.autocorrector import AutoCorrector
from sharkpad.spelling.underline import set_spellcheck_enabled


class EditMenu:
    def __init__(self, win):
        self.win = win
        editor, find_bar = win.editor, win.find_bar
        menu = win.menuBar().addMenu("&Edit")
        win.add_action(menu, "Undo (Ctrl+Z)", self.undo, ["Ctrl+Z"])
        win.add_action(menu, "Redo (Ctrl+Shift+Z)", self.redo, ["Ctrl+Y", "Ctrl+Shift+Z"])
        menu.addSeparator()
        win.add_action(menu, "Cut (Ctrl+X)", editor.cut)
        win.add_action(menu, "Copy (Ctrl+C)", editor.copy)
        win.add_action(menu, "Paste (Ctrl+V)", editor.paste)
        win.add_action(menu, "Select All (Ctrl+A)", editor.selectAll)
        menu.addSeparator()
        win.add_action(menu, "Find (Ctrl+F)", lambda: find_bar.open(), ["Ctrl+F"])
        win.add_action(menu, "Find Next (F3)", lambda: self.find_next(), ["F3"])
        win.add_action(menu, "Find Previous (Shift+F3)", lambda: self.find_next(backward=True), ["Shift+F3"])
        win.add_action(menu, "Replace (Ctrl+H)", lambda: find_bar.open(replace=True), ["Ctrl+H"])
        menu.addSeparator()
        win.add_action(menu, "Duplicate Line (Ctrl+D)", lambda: text_tools.duplicate_line(editor), ["Ctrl+D"])
        win.add_action(menu, "Move Line Up (Alt+Up)", lambda: text_tools.move_lines(editor, up=True), ["Alt+Up"])
        win.add_action(menu, "Move Line Down (Alt+Down)", lambda: text_tools.move_lines(editor, up=False), ["Alt+Down"])
        win.add_action(menu, "Insert Date and Time (F5)", lambda: text_tools.insert_date_time(editor), ["F5"])
        menu.addSeparator()

        editor.spellcheck_enabled = win.setting_bool("spell_check", True)
        win.add_action(menu, "Check Spelling", self.set_spell_check, checkable=True, checked=editor.spellcheck_enabled)

        self.autocorrector = AutoCorrector(editor)
        self.autocorrector.enabled = win.setting_bool("autocorrect", True)
        self.autocorrector.corrected.connect(lambda typed, fix: win.status_bar.showMessage(
            f"Autocorrected \"{typed}\" to \"{fix}\"  (Ctrl+Z puts it back)", 4000))
        self.autocorrector.rejected.connect(lambda typed: win.status_bar.showMessage(
            f"Got it, \"{typed}\" won't be autocorrected again.", 4000))
        win.add_action(menu, "Autocorrect While Typing", self.set_autocorrect,
                       checkable=True, checked=self.autocorrector.enabled)

    def _canvas_focused(self):
        return QApplication.focusWidget() is self.win.canvas

    def undo(self):
        if not self._canvas_focused():
            self.win.editor.undo()
        elif not self.win.canvas.undo():
            self.win.status_bar.showMessage("Nothing to undo on the drawing pad.", 2000)

    def redo(self):
        if not self._canvas_focused():
            self.win.editor.redo()
        elif not self.win.canvas.redo():
            self.win.status_bar.showMessage("Nothing to redo on the drawing pad.", 2000)

    def find_next(self, backward=False):
        find_bar = self.win.find_bar
        if not find_bar.find_edit.text():
            find_bar.open()
        else:
            find_bar.show()
            find_bar.find_next(backward=backward)

    def set_spell_check(self, on):
        self.win.settings.setValue("spell_check", on)
        set_spellcheck_enabled(self.win.editor, on)

    def set_autocorrect(self, on):
        self.autocorrector.enabled = on
        self.win.settings.setValue("autocorrect", on)
