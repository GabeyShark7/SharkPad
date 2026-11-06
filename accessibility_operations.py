import html
import os
import sys

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QDialog, QPushButton, QTextBrowser, QVBoxLayout

import edit_operations

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

        forced = os.environ.get("SHARKPAD_TTS_ENGINE")
        engines = [forced] if forced else [e for e in QTextToSpeech.availableEngines() if e != "mock"]
        for name in engines:
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
        if tts is None:
            self.error.emit(no_voice_help())
            return
        if not tts.availableVoices():
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
        edit_operations.set_selection_layer(self.editor, "speech", [])

    def _text_changed(self):
        if self.is_speaking():
            self.stop()

    def _state_changed(self, state):
        speaking = state == self._State.Speaking
        if not speaking:
            edit_operations.set_selection_layer(self.editor, "speech", [])
        if state == self._State.Error:
            self.error.emit(f"Read aloud stopped: {self.tts.errorString() or 'speech engine error'}")
        self.speaking_changed.emit(speaking)

    def _saying_word(self, word, _id, start, length):
        pos = self.base + start
        fmt = QTextCharFormat()
        fmt.setBackground(SPOKEN_WORD_COLOR)
        cursor = edit_operations.range_cursor(self.editor, pos, pos + length)
        edit_operations.set_selection_layer(self.editor, "speech", [edit_operations.make_selection(cursor, fmt)])

        rect = self.editor.cursorRect(cursor)
        view_h = self.editor.viewport().height()
        if rect.top() < 0 or rect.bottom() > view_h:
            line_h = max(1, self.editor.fontMetrics().lineSpacing())
            bar = self.editor.verticalScrollBar()
            bar.setValue(bar.value() + (rect.top() - view_h // 3) // line_h)


class HelpDialog(QDialog):
    """A readable, scrollable help page (works with screen readers)."""

    def __init__(self, parent, title, body_html):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(620, 560)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setAccessibleName(title)
        browser.setHtml(body_html)
        layout.addWidget(browser)
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)


def shortcuts_html(groups):
    """groups: [(group title, [(keys, description), ...]), ...]"""
    parts = ["<h2>Keyboard Shortcuts</h2>",
             "<p>On a Mac, use <b>Cmd</b> wherever this says <b>Ctrl</b>.</p>"]
    for title, rows in groups:
        parts.append(f"<h3>{html.escape(title)}</h3><table cellspacing='0' cellpadding='4' width='100%'>")
        for keys, desc in rows:
            parts.append(f"<tr><td width='42%'><b>{html.escape(keys)}</b></td><td>{html.escape(desc)}</td></tr>")
        parts.append("</table>")
    return "".join(parts)


GETTING_STARTED_HTML = """
<h2>Welcome to SharkPad</h2>
<p>SharkPad puts your notes, a drawing pad, and voice dictation in one window.</p>
<h3>Write</h3>
<ul>
<li>Type in the big box on the left. Obvious typos like "teh" fix themselves when you finish the word, and the fix flashes red for a moment. Press <b>Ctrl+Z</b> right away to keep what you typed.</li>
<li>Words SharkPad isn't sure about get a red wavy line; right-click one for suggestions. Turn either off in the <b>Edit</b> menu.</li>
<li>Made a mistake? <b>Ctrl+Z</b> undoes it and <b>Ctrl+Y</b> or <b>Ctrl+Shift+Z</b> brings it back.</li>
<li><b>Ctrl+F</b> finds words and <b>Ctrl+H</b> replaces them.</li>
<li><b>F5</b> stamps today's date and time, handy at the top of lecture notes.</li>
</ul>
<h3>Draw</h3>
<ul>
<li>Pick a tool on the drawing pad's toolbar: <b>Pen</b>, <b>Highlighter</b>, <b>Eraser</b>, <b>Text</b> or <b>Select</b>.
With the pad clicked, the keys <b>P</b>, <b>H</b>, <b>E</b>, <b>T</b> and <b>V</b> switch tools too.</li>
<li><b>Text:</b> click anywhere on the pad and type. Click away or press <b>Esc</b> when done. Double-click text to change it.</li>
<li><b>Select:</b> drag a box around things to select them, or Shift+click to add more. Drag to move, pull a corner to resize,
and use the arrow keys to nudge. <b>Delete</b> removes, <b>Ctrl+C</b>/<b>Ctrl+V</b> copy and paste, <b>Ctrl+D</b> duplicates.</li>
<li>Pick a color or size while something is selected to change it.</li>
<li>Click the pad first, then <b>Ctrl+Z</b> undoes and <b>Ctrl+Y</b> redoes.</li>
<li>The first time you press <b>Ctrl+S</b>, type a name. SharkPad makes a folder with that name and saves <b>Name_notes.txt</b> and, if you drew something, <b>Name_img.png</b> inside it.</li>
<li>Pick other file types (like .md notes or .jpg drawings) in <b>Preferences &gt; Save File Types</b>.</li>
</ul>
<h3>Listen</h3>
<ul>
<li>Press <b>Ctrl+Shift+V</b> and talk. SharkPad types what you say. Press it again to stop.</li>
<li>If it doesn't hear you, open <b>AI Tools &gt; Voice Dictation Settings</b> and use the live meter.</li>
</ul>
<h3>Learn</h3>
<ul>
<li><b>Ctrl+Shift+T</b> asks the AI Teacher to explain your notes (or just the part you selected).</li>
<li>Changed your mind? <b>Ctrl+Z</b> or <b>Restore original text</b> brings your notes back.</li>
<li><b>Ctrl+Shift+R</b> reads your notes out loud and highlights each word as it's spoken.</li>
</ul>
<h3>Never lose work</h3>
<ul>
<li>Tick <b>Autosave</b> in the top-right of the notes or the drawing pad to save every change automatically.</li>
<li>SharkPad also keeps a backup of unsaved notes every 30 seconds. If it closes unexpectedly,
it offers to bring them back next time.</li>
</ul>
"""

ACCESSIBILITY_HTML = """
<h2>Accessibility Features</h2>
<p>Everything here is in the <b>Accessibility</b> menu, and your choices are remembered.</p>
<h3>Reading</h3>
<ul>
<li><b>Read Aloud (Ctrl+Shift+R)</b> reads the selected text, or everything from the current paragraph.
The word being spoken is highlighted so you can follow along. Press it again or <b>Esc</b> to stop.</li>
<li><b>Reading Speed</b> and <b>Voice</b> change how it sounds.</li>
<li><b>Reading Guide</b> tints the line you're on, like a ruler under the line.</li>
</ul>
<h3>Seeing the text</h3>
<ul>
<li><b>Dyslexia Font</b> switches to OpenDyslexic, a font with weighted letter bottoms.</li>
<li><b>Text Spacing</b> adds space between letters and words, which helps many readers.</li>
<li><b>Ctrl+=</b> and <b>Ctrl+-</b> (or Ctrl + mouse wheel) make text bigger or smaller. <b>Ctrl+0</b> resets it.</li>
<li><b>Preferences &gt; Color Scheme</b> has <b>High Contrast</b> (white on black) and <b>Cream</b> (low glare).</li>
<li><b>Thick Text Cursor</b> makes the blinking cursor easier to spot.</li>
</ul>
<h3>Focus</h3>
<ul>
<li><b>Focus Mode (F11)</b> goes full screen and hides the drawing pad. Press F11 or Esc to leave.</li>
</ul>
<h3>Keyboard and screen readers</h3>
<ul>
<li>Every feature has a menu item, and most have a shortcut (see <b>Help &gt; Keyboard Shortcuts</b>).</li>
<li>Press <b>Alt</b> to reach the menus from the keyboard.</li>
<li>Controls are labeled for screen readers such as NVDA, JAWS, Narrator and VoiceOver.</li>
</ul>
"""

DICTATION_HELP_HTML = """
<h2>Voice Dictation Help</h2>
<h3>Getting started</h3>
<ol>
<li>Open <b>AI Tools &gt; Voice Dictation Settings</b>.</li>
<li>Pick your microphone, then talk normally. The bar should turn green and pass the dashed line.</li>
<li>If it doesn't, click a room preset or drag <b>Sensitivity</b> toward <b>High</b>.</li>
<li>Close the window and press <b>Ctrl+Shift+V</b>. Talk, then pause briefly: your words appear after each pause.</li>
</ol>
<h3>Speed or accuracy</h3>
<p>In the settings, <b>Fast</b> suits older computers, <b>Balanced</b> suits most, and <b>Accurate</b> makes the
fewest mistakes but needs a quick computer. Each model downloads once the first time you use it.</p>
<h3>Nothing is typed</h3>
<ul>
<li>Check the status bar at the bottom of the window for messages.</li>
<li><b>Windows:</b> Settings &gt; Privacy &amp; security &gt; Microphone: allow desktop apps.</li>
<li><b>Mac:</b> System Settings &gt; Privacy &amp; Security &gt; Microphone: allow SharkPad.</li>
<li><b>Linux:</b> install PortAudio with <code>sudo apt install libportaudio2</code>.</li>
</ul>
<p>Speech recognition runs on your own computer. Your voice is never uploaded.</p>
"""


def about_html(version=""):
    return f"""
<h2>SharkPad {html.escape(version)}</h2>
<p>Notes, drawing, and voice dictation in one window. Built for students who need to type,
sketch, and listen at the same time.</p>
<p>Speech recognition by Whisper (runs offline). AI Teacher by Groq.
Dyslexia font: OpenDyslexic.</p>
<p><a href="https://github.com/GabeyShark7/SharkPad">github.com/GabeyShark7/SharkPad</a></p>
"""
