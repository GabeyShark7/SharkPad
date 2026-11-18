import os

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from sharkpad.files import project, recovery
from sharkpad.window.autosave import Autosave
from sharkpad.window.crash_backup import CrashBackup
from sharkpad.window.recent_files import RecentFiles

OPEN_FILTER = "SharkPad Notes (*_notes.txt *_notes.md *_notes.html);;Text Files (*.txt *.md *.html);;All Files (*)"


class FileMenu:
    def __init__(self, win):
        self.win = win
        self.recent = RecentFiles(win, self.open_note)
        self.autosave = Autosave(win, self)
        self.backup = CrashBackup(win)

        menu = win.menuBar().addMenu("&File")
        win.add_action(menu, "New (Ctrl+N)", self.new_note, ["Ctrl+N"])
        win.add_action(menu, "Open (Ctrl+O)", lambda: self.open_note(), ["Ctrl+O"])
        menu.addMenu(self.recent.menu)
        menu.addSeparator()
        win.add_action(menu, "Save (Ctrl+S)", self.save, ["Ctrl+S"])
        win.add_action(menu, "Save As (Ctrl+Shift+S)", self.save_as, ["Ctrl+Shift+S"])
        menu.addSeparator()
        win.add_action(menu, "Export as PDF...", self.export_pdf)
        win.add_action(menu, "Print (Ctrl+P)", self.print_note, ["Ctrl+P"])
        menu.addSeparator()
        win.add_action(menu, "Exit (Ctrl+Q)", win.close, ["Ctrl+Q"])

    def current_project(self):
        path = self.win.current_file
        if path and project.is_project_notes(path):
            return project.split_project(path)
        return None

    def write_project(self, folder, name, notes=True, image=True, force=False):
        win = self.win
        editor, canvas = win.editor, win.canvas
        notes_file = project.notes_path(folder, name, project.chosen_notes_ext(win.settings))
        image_file = project.image_path(folder, name, project.chosen_image_ext(win.settings))
        try:
            os.makedirs(folder, exist_ok=True)
            if notes:
                if force or editor.document().isModified() or not os.path.exists(notes_file):
                    project.write_notes(notes_file, editor.toPlainText(), name)
                project.remove_other_versions(folder, name, notes_file)
                editor.document().setModified(False)
            if image:
                if canvas.items:
                    if force or canvas.modified or not os.path.exists(image_file):
                        project.write_image(canvas, image_file)
                    project.remove_other_versions(folder, name, image_file, images=True)
                else:
                    project.remove_other_versions(folder, name, None, images=True)
                canvas.modified = False
                canvas.changed.emit()
        except OSError as e:
            QMessageBox.critical(win, "Couldn't Save", f"Could not save to {folder}:\n{e}")
            return False
        if notes:
            recovery.clear()
            if os.path.normcase(notes_file) != os.path.normcase(win.current_file or ""):
                win.current_file = notes_file
                self.recent.add(notes_file)
        self.autosave.mark_saved(notes, image)
        win.update_title()
        return True

    def save_as(self):
        win = self.win
        current = self.current_project()
        if current:
            start_dir, suggested = os.path.dirname(current[0]), current[1]
        else:
            start_dir = os.path.join(os.path.expanduser("~"), "Documents")
            suggested = project.clean_name(win.current_file) if win.current_file else "My Notes"
        chosen, _ = QFileDialog.getSaveFileName(
            win, "Save - name your notes (they go in a folder with this name)",
            os.path.join(start_dir, suggested), "SharkPad folder (*)",
            options=QFileDialog.DontConfirmOverwrite)
        if not chosen:
            return False
        folder, name = project.project_from_choice(chosen)
        same_project = bool(current) and os.path.normcase(folder) == os.path.normcase(current[0]) and name == current[1]
        if not same_project and project.existing_files(folder, name):
            reply = QMessageBox.question(
                win, "Replace Saved Notes?",
                f"\"{name}\" already has saved notes in:\n{folder}\n\nReplace them?")
            if reply != QMessageBox.Yes:
                return False
        if not self.write_project(folder, name, force=True):
            return False
        win.status_bar.showMessage(f"Saved \"{name}\" in {folder}", 4000)
        return True

    def save(self):
        current = self.current_project()
        if not current:
            return self.save_as()
        if not self.write_project(*current):
            return False
        self.win.status_bar.showMessage(f"Saved \"{current[1]}\"", 3000)
        return True

    def maybe_save(self):
        """Ask to save unsaved work. Returns False if the user cancels."""
        win = self.win
        if not win.is_dirty():
            return True
        name = win.display_name() if win.current_file else "this note"
        box = QMessageBox(QMessageBox.Warning, "Unsaved Changes",
                          f"Do you want to save your changes to {name}?",
                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, win)
        box.setInformativeText("If you don't save, your changes will be lost.")
        box.setDefaultButton(QMessageBox.Save)
        reply = box.exec()
        if reply == QMessageBox.Save:
            return self.save()
        return reply == QMessageBox.Discard

    def _reset_document(self):
        self.win.ai_menu.clear_restore()
        recovery.clear()
        self.win.update_title()

    def new_note(self):
        if not self.maybe_save():
            return
        win = self.win
        win.read_aloud.stop()
        win.editor.clear()
        win.canvas.clear_canvas()
        win.editor.document().setModified(False)
        win.current_file = None
        self._reset_document()

    def open_note(self, path=None):
        if not self.maybe_save():
            return
        win = self.win
        if not path:
            start = os.path.dirname(win.current_file) if win.current_file else ""
            path, _ = QFileDialog.getOpenFileName(win, "Open Notes", start, OPEN_FILTER)
        if not path:
            return
        try:
            text = project.read_notes(path)
        except OSError as e:
            QMessageBox.critical(win, "Couldn't Open", f"Could not open the file:\n{e}")
            self.recent.remove(path)
            return
        win.read_aloud.stop()
        win.editor.setPlainText(text)
        win.editor.document().setModified(False)
        image_file = project.find_image(path)
        if image_file:
            win.canvas.load(image_file)
        else:
            win.canvas.clear_canvas()
        win.current_file = path
        self.recent.add(path)
        self._reset_document()
        self.autosave.show_opened()
        win.status_bar.showMessage(f"Opened \"{win.display_name()}\"", 3000)

    def print_note(self):
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        printer = QPrinter(QPrinter.HighResolution)
        if QPrintDialog(printer, self.win).exec() == QDialog.Accepted:
            self.win.editor.document().print_(printer)

    def export_pdf(self):
        from PySide6.QtPrintSupport import QPrinter
        win = self.win
        default = os.path.splitext(win.current_file)[0] + ".pdf" if win.current_file else "Notes.pdf"
        path, _ = QFileDialog.getSaveFileName(win, "Export as PDF", default, "PDF Files (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        win.editor.document().print_(printer)
        win.status_bar.showMessage(f"Exported {os.path.basename(path)}", 3000)

    def before_close(self):
        self.autosave.flush()
        if not self.maybe_save():
            return False
        self.win.read_aloud.stop()
        recovery.clear()
        return True
