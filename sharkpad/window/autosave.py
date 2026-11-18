import time

from PySide6.QtCore import QTimer

AUTOSAVE_DELAY_MS = 1500


def saved_stamp():
    return "Saved " + time.strftime("%I:%M %p").lstrip("0")


class Autosave:
    def __init__(self, win, files):
        self.win = win
        self.files = files
        self.boxes = {True: win.notes_autosave, False: win.drawing_pad.autosave}
        self.timers = {}
        for is_notes, box in self.boxes.items():
            timer = QTimer(win)
            timer.setSingleShot(True)
            timer.setInterval(AUTOSAVE_DELAY_MS)
            timer.timeout.connect(lambda n=is_notes: self.save_now(n))
            self.timers[is_notes] = timer
            box.setChecked(win.setting_bool(self._key(is_notes), False))
            box.toggled.connect(lambda on, n=is_notes: self.toggle(n, on))
        win.editor.textChanged.connect(lambda: self.content_changed(True))
        win.canvas.changed.connect(lambda: self.content_changed(False))

    def _key(self, notes):
        return "autosave_notes" if notes else "autosave_drawing"

    def _has_changes(self, notes):
        return self.win.editor.document().isModified() if notes else self.win.canvas.modified

    def save_now(self, notes):
        project = self.files.current_project()
        if self.boxes[notes].isChecked() and project and self._has_changes(notes):
            self.files.write_project(*project, notes=notes, image=not notes)

    def content_changed(self, notes):
        box = self.boxes[notes]
        if not box.isChecked():
            return
        if not self.files.current_project():
            box.set_status("Save once (Ctrl+S) to start")
            return
        if self._has_changes(notes):
            box.set_status("Editing...")
            self.timers[notes].start()

    def toggle(self, notes, on):
        box = self.boxes[notes]
        self.win.settings.setValue(self._key(notes), on)
        if not on:
            self.timers[notes].stop()
            box.set_status("")
            return
        if not self.files.current_project() and not self.files.save_as():
            box.setChecked(False)
            self.win.settings.setValue(self._key(notes), False)
            return
        self.save_now(notes)
        box.set_status(saved_stamp())

    def mark_saved(self, notes, image):
        for is_notes, saved in ((True, notes), (False, image)):
            if saved and self.boxes[is_notes].isChecked():
                self.boxes[is_notes].set_status(saved_stamp())

    def show_opened(self):
        for box in self.boxes.values():
            box.set_status(saved_stamp() if box.isChecked() and self.files.current_project() else "")

    def flush(self):
        for is_notes, timer in self.timers.items():
            if timer.isActive():
                timer.stop()
                self.save_now(is_notes)
