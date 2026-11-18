import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QTextCharFormat

from sharkpad.editor.highlights import make_selection, set_selection_layer
from sharkpad.editor.text_tools import range_cursor

READING_RATES = [("Slow", -0.35), ("Normal", 0.0), ("Fast", 0.35)]
SPOKEN_WORD_COLOR = QColor(100, 181, 246, 160)


def no_voice_help():
    if sys.platform == "win32":
        return ("Your computer has no text-to-speech voices installed.\n\n"
                "Open Windows Settings > Time & language > Speech. Under \"Manage voices\", "
                "click \"Add voices\" and install one (for example English (United States)). "
                "Then restart SharkPad.")
    if sys.platform == "darwin":
        return ("Your Mac didn't offer a text-to-speech voice.\n\n"
                "Open System Settings > Accessibility > Spoken Content and pick a System Voice, "
                "then restart SharkPad.")
    return ("No text-to-speech engine was found.\n\n"
            "Install one with: sudo apt install speech-dispatcher espeak-ng\n"
            "Then restart SharkPad.")


class ReadAloud(QObject):
    """Reads the selection (or the text from the cursor's paragraph) out loud."""

    speaking_changed = Signal(bool)
    error = Signal(str)

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.tts = None
        self.base = 0
        self.rate = 0.0
        self.voice_name = ""
        self._failed = False
        editor.textChanged.connect(self._text_changed)

    def _engine(self):
        """Pick the first working speech engine (loaded on first use, not at startup)."""
        if self.tts is not None or self._failed:
            return self.tts
        from PySide6.QtTextToSpeech import QTextToSpeech

        for name in QTextToSpeech.availableEngines():
            if name == "mock":
                continue
            tts = QTextToSpeech(name, self)
            if tts.state() != QTextToSpeech.State.Error:
                self.tts = tts
                break
            tts.deleteLater()
        if self.tts is None:
            self._failed = True
            return None

        self._State = QTextToSpeech.State
        self.tts.stateChanged.connect(self._state_changed)
        self.tts.sayingWord.connect(self._saying_word)
        self.tts.setRate(self.rate)
        self._apply_voice()
        return self.tts

    def voices(self):
        tts = self._engine()
        return [v.name() for v in tts.availableVoices()] if tts else []

    def set_voice(self, name):
        self.voice_name = name or ""
        if self.tts:
            self._apply_voice()

    def _apply_voice(self):
        for v in self.tts.availableVoices():
            if v.name() == self.voice_name:
                self.tts.setVoice(v)
                return

    def set_rate(self, rate):
        self.rate = rate
        if self.tts:
            self.tts.setRate(rate)

    def is_speaking(self):
        return self.tts is not None and self.tts.state() == self._State.Speaking

    def toggle(self):
        if self.is_speaking():
            self.stop()
        else:
            self.read()

    def read(self):
        tts = self._engine()
        if tts is None or not tts.availableVoices():
            self.error.emit(no_voice_help())
            return

        text = self.editor.toPlainText()
        c = self.editor.textCursor()
        if c.hasSelection():
            start, end = c.selectionStart(), c.selectionEnd()
        elif c.position() >= len(text.rstrip()):
            start, end = 0, len(text)
        else:
            start, end = c.block().position(), len(text)

        chunk = text[start:end]
        if not chunk.strip():
            self.error.emit("There's no text to read yet.")
            return
        self.base = start
        tts.say(chunk)

    def stop(self):
        if self.tts:
            self.tts.stop()
        set_selection_layer(self.editor, "speech", [])

    def _text_changed(self):
        if self.is_speaking():
            self.stop()

    def _state_changed(self, state):
        speaking = state == self._State.Speaking
        if not speaking:
            set_selection_layer(self.editor, "speech", [])
        if state == self._State.Error:
            self.error.emit(f"Read aloud stopped: {self.tts.errorString() or 'speech engine error'}")
        self.speaking_changed.emit(speaking)

    def _saying_word(self, word, _id, start, length):
        pos = self.base + start
        fmt = QTextCharFormat()
        fmt.setBackground(SPOKEN_WORD_COLOR)
        cursor = range_cursor(self.editor, pos, pos + length)
        set_selection_layer(self.editor, "speech", [make_selection(cursor, fmt)])

        rect = self.editor.cursorRect(cursor)
        view_h = self.editor.viewport().height()
        if rect.top() < 0 or rect.bottom() > view_h:
            line_h = max(1, self.editor.fontMetrics().lineSpacing())
            bar = self.editor.verticalScrollBar()
            bar.setValue(bar.value() + (rect.top() - view_h // 3) // line_h)
