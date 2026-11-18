from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QMessageBox

from sharkpad.editor.editor_font import DYSLEXIA_MODES, TEXT_SPACING
from sharkpad.editor.highlights import update_reading_guide
from sharkpad.editor.read_aloud import READING_RATES
from sharkpad.shortcut_hints import set_hinted_text


class AccessibilityMenu:
    def __init__(self, win):
        self.win = win
        settings, read_aloud, font = win.settings, win.read_aloud, win.editor_font
        menu = win.menuBar().addMenu("&Accessibility")

        rate_name = settings.value("tts_rate", "Normal")
        read_aloud.set_rate(dict(READING_RATES).get(rate_name, 0.0))
        read_aloud.set_voice(settings.value("tts_voice", "") or "")
        self.read_action = win.add_action(menu, "Read Aloud (Ctrl+Shift+R)", read_aloud.toggle, ["Ctrl+Shift+R"])
        read_aloud.error.connect(lambda msg: QMessageBox.information(win, "Read Aloud", msg))
        read_aloud.speaking_changed.connect(self._reading_changed)

        win.add_choice_menu(menu, "Reading Speed", [(label, label) for label, _rate in READING_RATES], rate_name,
                            self._set_rate)
        self.voice_menu = menu.addMenu("Voice")
        self.voice_menu.aboutToShow.connect(self._fill_voice_menu)
        menu.addSeparator()

        win.add_choice_menu(menu, "Dyslexia Font", [(m, m) for m in DYSLEXIA_MODES], font.dyslexia, font.set_dyslexia)
        win.add_choice_menu(menu, "Text Spacing", [(n, n) for n in TEXT_SPACING], font.spacing, font.set_spacing)

        self.guide_on = win.setting_bool("reading_guide", False)
        win.editor.cursorPositionChanged.connect(lambda: update_reading_guide(win.editor, self.guide_on))
        win.add_action(menu, "Reading Guide (highlight current line)", self.set_reading_guide,
                       checkable=True, checked=self.guide_on)
        update_reading_guide(win.editor, self.guide_on)

        thick = win.setting_bool("thick_cursor", False)
        self.set_thick_cursor(thick)
        win.add_action(menu, "Thick Text Cursor", self.set_thick_cursor, checkable=True, checked=thick)
        menu.addSeparator()

        self.theme_before_contrast = win.theme if win.theme != "High Contrast" else "Light"
        self.high_contrast_action = win.add_action(menu, "High Contrast Colors", self.toggle_high_contrast,
                                                   checkable=True, checked=win.theme == "High Contrast")

    def _reading_changed(self, on):
        set_hinted_text(self.read_action, "Stop Reading (Ctrl+Shift+R)" if on else "Read Aloud (Ctrl+Shift+R)",
                        self.win.show_hints)
        if on:
            self.win.status_bar.showMessage("Reading aloud... press Esc or Ctrl+Shift+R to stop.")
        else:
            self.win.status_bar.clearMessage()

    def _set_rate(self, label):
        self.win.read_aloud.set_rate(dict(READING_RATES)[label])
        self.win.settings.setValue("tts_rate", label)

    def _fill_voice_menu(self):
        self.voice_menu.clear()
        voices = self.win.read_aloud.voices()
        if not voices:
            none = self.voice_menu.addAction("No voices installed (see Help > Accessibility)")
            none.setEnabled(False)
            return
        current = self.win.settings.value("tts_voice", "") or ""
        group = QActionGroup(self.voice_menu)
        for name in [""] + voices:
            a = self.voice_menu.addAction(name or "System default")
            a.setCheckable(True)
            a.setChecked(name == current)
            group.addAction(a)
            a.triggered.connect(lambda _=False, n=name: self._set_voice(n))

    def _set_voice(self, name):
        self.win.read_aloud.set_voice(name)
        self.win.settings.setValue("tts_voice", name)

    def set_reading_guide(self, on):
        self.guide_on = on
        self.win.settings.setValue("reading_guide", on)
        update_reading_guide(self.win.editor, on)

    def set_thick_cursor(self, on):
        self.win.editor.setCursorWidth(3 if on else 1)
        self.win.settings.setValue("thick_cursor", on)

    def toggle_high_contrast(self, on):
        if on:
            self.theme_before_contrast = self.win.theme
            self.win.preferences_menu.set_theme("High Contrast")
        else:
            previous = self.theme_before_contrast
            self.win.preferences_menu.set_theme(previous if previous != "High Contrast" else "Light")

    def theme_changed(self, theme):
        self.high_contrast_action.blockSignals(True)
        self.high_contrast_action.setChecked(theme == "High Contrast")
        self.high_contrast_action.blockSignals(False)
        update_reading_guide(self.win.editor, self.guide_on)
