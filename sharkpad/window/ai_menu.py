from PySide6.QtGui import QAction, QTextCursor
from PySide6.QtWidgets import QMessageBox, QPushButton

from sharkpad.ai_teacher import instructions, teacher
from sharkpad.ai_teacher.ai_glow import AiGlow
from sharkpad.ai_teacher.settings_dialog import TeacherSettingsDialog
from sharkpad.editor.text_tools import replace_all_text, replace_range
from sharkpad.shortcut_hints import set_hinted_text
from sharkpad.voice import dictation, mic, speech_model
from sharkpad.voice.settings_dialog import VoiceSettingsDialog
from sharkpad.window.ask_question import AskQuestion

AI_HEADER = "AI Teacher explanation:\n"


class AiMenu:
    def __init__(self, win):
        self.win = win
        self.voice_dialog = None
        self.before_ai = None
        self.after_ai = None
        self.explain_range = None
        self.doc_at_start = None
        self.blocks = []
        self._load_saved_settings()
        self.glow = AiGlow(win.editor)
        self.ask = AskQuestion(win)

        self.restore_btn = QPushButton("Restore original text")
        self.restore_btn.setToolTip("Bring back your notes as they were before the AI Teacher explanation")
        self.restore_btn.hide()
        self.restore_btn.clicked.connect(self.restore_original)
        win.status_bar.addPermanentWidget(self.restore_btn)

        menu = win.menuBar().addMenu("AI &Tools")
        win.add_action(menu, "AI Teacher Settings (Token)...", lambda: TeacherSettingsDialog(win, win.settings).exec())
        menu.addSeparator()
        self.voice_action = win.add_action(menu, "Voice Dictation (Ctrl+Shift+V)", self.toggle_voice, ["Ctrl+Shift+V"])
        win.add_action(menu, "Voice Dictation Settings...", self.show_voice_settings)
        menu.addSeparator()
        self.explain_action = win.add_action(menu, "AI Teacher Explain (Ctrl+Shift+T)", self.explain, ["Ctrl+Shift+T"])
        win.add_action(menu, "Ask a Question... (Ctrl+Shift+Q)", self.ask.open, ["Ctrl+Shift+Q"])
        win.add_action(menu, "Insert AI Instruction (Ctrl+Shift+I)", self.insert_instruction, ["Ctrl+Shift+I"])
        self.keep_notes_action = win.add_action(
            menu, "Keep My Notes (add explanation below)", lambda on: win.settings.setValue("ai_keep_notes", on),
            checkable=True, checked=win.setting_bool("ai_keep_notes", False))
        self.restore_action = win.add_action(menu, "Restore Original Text", self.restore_original)
        self.restore_action.setEnabled(False)

        read_ctx = QAction("Read Aloud", win)
        read_ctx.triggered.connect(win.read_aloud.toggle)
        explain_ctx = QAction("Explain with AI Teacher", win)
        explain_ctx.triggered.connect(self.explain)
        ask_ctx = QAction("Ask a Question...", win)
        ask_ctx.triggered.connect(self.ask.open)
        win.editor.extra_context_actions = [ask_ctx, explain_ctx, read_ctx]

    def _load_saved_settings(self):
        settings = self.win.settings
        try:
            mic.set_sensitivity(int(settings.value("mic_sensitivity", mic.DEFAULT_SENSITIVITY)))
        except (TypeError, ValueError):
            mic.set_sensitivity(mic.DEFAULT_SENSITIVITY)
        mic.set_device(settings.value("mic_device", "") or "")
        speech_model.set_quality(settings.value("dictation_quality", speech_model.DEFAULT_QUALITY))
        saved_token = settings.value("api_key")
        if saved_token:
            teacher.set_api_token(saved_token)
        teacher.set_preset(settings.value("teacher_preset", ""))

    def _set_voice_ui(self, is_on):
        self.win.listening = is_on
        set_hinted_text(self.voice_action,
                        "Stop Dictation (Ctrl+Shift+V)" if is_on else "Voice Dictation (Ctrl+Shift+V)",
                        self.win.show_hints)
        self.win.update_title()

    def _voice_status(self, msg):
        self.win.status_bar.showMessage(f"Dictation: {msg}")

    def _voice_error(self, msg):
        self.win.status_bar.clearMessage()
        QMessageBox.warning(self.win, "Voice Dictation", msg)

    def _voice_stopped(self):
        self._set_voice_ui(dictation.is_voice_active())
        if not dictation.is_voice_active():
            self.win.status_bar.showMessage("Dictation stopped.", 3000)

    def toggle_voice(self):
        is_on = dictation.toggle_voice(self.win.editor, self._voice_status, self._voice_error, self._voice_stopped)
        self._set_voice_ui(is_on)
        if is_on:
            self.win.settings.setValue("dictation_used", True)
        else:
            self.win.status_bar.showMessage("Dictation stopped.", 3000)

    def show_voice_settings(self):
        if not self.voice_dialog:
            self.voice_dialog = VoiceSettingsDialog(self.win, self.win.settings)
        self.voice_dialog.show()
        self.voice_dialog.raise_()
        self.voice_dialog.activateWindow()

    def explain(self):
        win = self.win
        if teacher.is_busy():
            win.status_bar.showMessage("The AI Teacher is still working on the last explanation...", 3000)
            return
        text = win.editor.toPlainText()
        self.doc_at_start = text
        self.blocks = instructions.find_blocks(text)
        if self.blocks:
            count = len(self.blocks)
            self._start_thinking(f"AI Teacher is following {count} instruction{'s' if count > 1 else ''}... "
                                 "you can keep working.")
            blocks = self.blocks
            teacher.run_async(lambda: teacher.follow_all(blocks), self._instructed)
            return
        c = win.editor.textCursor()
        start, end = (c.selectionStart(), c.selectionEnd()) if c.hasSelection() else (0, len(text))
        chunk = text[start:end]
        if not chunk.strip():
            QMessageBox.information(win, "No Text", "Please write or select some notes for me to explain!")
            return
        self.explain_range = (start, end)
        self._start_thinking("AI Teacher is thinking... you can keep working.")
        teacher.run_async(lambda: teacher.explain(chunk), self._explained)

    def _start_thinking(self, message):
        self.win.thinking = True
        self.explain_action.setEnabled(False)
        self.win.update_title()
        self.win.status_bar.showMessage(message)

    def _done_thinking(self, ok, error):
        win = self.win
        win.thinking = False
        self.explain_action.setEnabled(True)
        win.update_title()
        if not ok:
            win.status_bar.clearMessage()
            QMessageBox.warning(win, "AI Teacher", error)
        return ok

    def _remember_before(self, before):
        self.before_ai = before
        self.after_ai = self.win.editor.toPlainText()
        self.restore_action.setEnabled(True)
        self.restore_btn.show()

    def insert_instruction(self):
        editor = self.win.editor
        c = editor.textCursor()
        selected = c.selectedText().replace(" ", "\n")
        c.beginEditBlock()
        start = c.selectionStart()
        c.insertText(f"{instructions.START_TEMPLATE}\n{selected}\n{instructions.END_MARKER}")
        c.endEditBlock()
        c.setPosition(start + instructions.START_TEMPLATE.index("$ ") + 2)
        editor.setTextCursor(c)
        editor.setFocus()
        self.win.status_bar.showMessage(
            "Type what you want between the $ signs, then press Ctrl+Shift+T.", 6000)

    def _instructed(self, ok, results):
        if not self._done_thinking(ok, results):
            return
        win = self.win
        current = win.editor.toPlainText()
        unchanged = current == self.doc_at_start
        edits = []
        for block, result in zip(self.blocks, results):
            start = block.start if unchanged else current.find(block.full_text)
            if start >= 0:
                edits.append((start, start + len(block.full_text), result))
        c = QTextCursor(win.editor.document())
        c.beginEditBlock()
        for start, end, result in sorted(edits, reverse=True):
            c.setPosition(start)
            c.setPosition(end, QTextCursor.KeepAnchor)
            c.insertText(result)
        c.endEditBlock()
        self._remember_before(current)
        skipped = len(self.blocks) - len(edits)
        note = f" {skipped} block(s) changed while it worked, so they were left alone." if skipped else ""
        win.status_bar.showMessage(
            f"Done! Ctrl+Z or \"Restore original text\" brings back your notes.{note}", 10000)

    def _explained(self, ok, result):
        if not self._done_thinking(ok, result):
            return
        win = self.win
        before = win.editor.toPlainText()
        start, end = self.explain_range
        if before != self.doc_at_start:
            replace_range(win.editor, len(before), len(before), "\n\n" + AI_HEADER + result)
        elif self.keep_notes_action.isChecked():
            replace_range(win.editor, end, end, "\n\n" + AI_HEADER + result)
        else:
            replace_range(win.editor, start, end, result)
        self._remember_before(before)
        win.status_bar.showMessage("Explanation added. Ctrl+Z or \"Restore original text\" brings back your notes.", 10000)

    def restore_original(self):
        win = self.win
        if self.before_ai is None:
            return
        if win.editor.toPlainText() != self.after_ai:
            reply = QMessageBox.question(
                win, "Restore Original Text",
                "You've changed the text since the explanation was added. Restoring brings your notes back "
                "exactly as they were before the explanation, so those changes go too (Ctrl+Z can undo the restore).\n\n"
                "Restore anyway?")
            if reply != QMessageBox.Yes:
                return
        replace_all_text(win.editor, self.before_ai)
        self.clear_restore()
        win.status_bar.showMessage("Your original text is back.", 4000)

    def clear_restore(self):
        self.before_ai = self.after_ai = None
        self.restore_action.setEnabled(False)
        self.restore_btn.hide()
