import os

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from sharkpad.files import recovery

BACKUP_EVERY_MS = 30000


class CrashBackup:
    def __init__(self, win):
        self.win = win
        timer = QTimer(win)
        timer.timeout.connect(self.backup)
        timer.start(BACKUP_EVERY_MS)

    def backup(self):
        if self.win.editor.document().isModified():
            recovery.save(self.win.editor.toPlainText(), self.win.current_file)

    def offer_recovery(self):
        data = recovery.load()
        if not data:
            return
        name = os.path.basename(data["file"]) if data.get("file") else "an unsaved note"
        when = data.get("saved_at", "").replace("T", " at ")
        reply = QMessageBox.question(
            self.win, "Recover Unsaved Notes",
            f"SharkPad closed before {name} was saved (last backup {when}).\n\nBring those notes back?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply != QMessageBox.Yes:
            recovery.clear()
            return
        win = self.win
        win.editor.setPlainText(data["text"])
        path = data.get("file")
        win.current_file = path if path and os.path.exists(os.path.dirname(path)) else None
        win.editor.document().setModified(True)
        win.update_title()
        win.status_bar.showMessage("Notes recovered. Save them to keep them.", 6000)
