import sys
import os
import time
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPlainTextEdit, QMenu, QWidget, QHBoxLayout, QVBoxLayout,
    QFileDialog, QMessageBox, QLabel, QSlider, QDialog, QPushButton, QLineEdit, QComboBox, QInputDialog
)
from PySide6.QtGui import (
    QFont, QFontDatabase, QAction, QActionGroup, QKeySequence, QShortcut, QIcon, QPainter, QPen,
    QColor, QPalette, QDesktopServices
)
from PySide6.QtCore import Qt, QTimer, QSettings, QUrl

import accessibility_operations
import edit_operations
import preferences_operations
import project_operations
import recovery_operations
import ai_operations
import voice_operations
import drawing_operations
import summarization_operations
from splash import SplashScreen


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class OpenAISettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Teacher Settings")
        self.setFixedWidth(450)
        self.settings = QSettings("SharkPadApp", "Settings")
        layout = QVBoxLayout(self)

        title_label = QLabel("Setup AI Teacher")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title_label)

        step1_label = QLabel("Step 1: Get your free API key")
        step1_label.setStyleSheet("font-size: 12px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(step1_label)

        link_label = QLabel('<a href="https://console.groq.com/keys">Click here to get a free Groq API key</a>')
        link_label.setOpenExternalLinks(True)
        link_label.setStyleSheet("font-size: 11px; margin-left: 10px;")
        layout.addWidget(link_label)

        instruction_label = QLabel("(Sign up or log in, then create a new API key)")
        instruction_label.setStyleSheet("font-size: 10px; color: gray; margin-left: 10px;")
        layout.addWidget(instruction_label)

        step2_label = QLabel("Step 2: Enter your API key below")
        step2_label.setStyleSheet("font-size: 12px; font-weight: bold; margin-top: 15px;")
        layout.addWidget(step2_label)

        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setPlaceholderText("gsk_...")

        saved_token = self.settings.value("api_key", "")
        self.token_input.setText(saved_token)
        layout.addWidget(self.token_input)

        info_label = QLabel("Your key is saved locally and remembered for next time.")
        info_label.setStyleSheet("font-size: 10px; color: gray;")
        layout.addWidget(info_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save Key")
        save_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; padding: 5px 15px;")
        save_btn.clicked.connect(self.save_token)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addSpacing(15)
        layout.addLayout(btn_layout)

    def save_token(self):
        token = self.token_input.text().strip()
        if not token.startswith("gsk_"):
            QMessageBox.warning(self, "Invalid Key", "Groq API keys must start with 'gsk_'.\n\nPlease check your key and try again.")
            return
        self.settings.setValue("api_key", token)
        summarization_operations.set_api_token(token)
        QMessageBox.information(self, "Success", "Groq API Key saved successfully!\n\nYou can now use AI Teacher features.")
        self.accept()

class LevelMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.level = 0
        self.trigger = 40
        self.setMinimumHeight(26)

    def set_values(self, level, trigger):
        if (level, trigger) != (self.level, self.trigger):
            self.level, self.trigger = level, trigger
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        pal = self.palette()
        p.setPen(pal.color(QPalette.Mid))
        p.setBrush(pal.color(QPalette.Base))
        p.drawRoundedRect(r, 4, 4)

        heard = self.level >= self.trigger
        fill = QColor("#2e7d32") if heard else QColor("#9e9e9e")
        w = int(r.width() * self.level / 100)
        if w > 0:
            p.setPen(Qt.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(r.x(), r.y(), w, r.height(), 4, 4)

        x = r.x() + int(r.width() * self.trigger / 100)
        p.setPen(QPen(pal.color(QPalette.Text), 2, Qt.DashLine))
        p.drawLine(x, r.top() - 1, x, r.bottom() + 1)
        p.end()


class VoiceSettingsDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Voice Dictation Settings")
        self.setModal(False)
        self.setFixedWidth(500)
        self.monitor = voice_operations.MicMonitor()

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("<b>Microphone</b>"))
        self.device_box = QComboBox()
        self.device_box.addItem("System default", "")
        for name in voice_operations.list_input_devices():
            self.device_box.addItem(name, name)
        idx = self.device_box.findData(voice_operations.get_device())
        self.device_box.setCurrentIndex(max(0, idx))
        self.device_box.currentIndexChanged.connect(self._device_changed)
        layout.addWidget(self.device_box)

        layout.addWidget(QLabel("<b>Where are you?</b> Pick one to set the slider for you."))
        preset_row = QHBoxLayout()
        self.preset_buttons = {}
        for label, value, tip in voice_operations.PRESETS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setAutoDefault(False)
            btn.setToolTip(tip)
            btn.setStyleSheet(
                "QPushButton:checked { background-color: palette(highlight);"
                " color: palette(highlighted-text); font-weight: bold; }"
            )
            btn.clicked.connect(lambda _=False, v=value: self.slider.setValue(v))
            self.preset_buttons[value] = btn
            preset_row.addWidget(btn)
        layout.addLayout(preset_row)
        self.preset_hint = QLabel()
        self.preset_hint.setWordWrap(True)
        self.preset_hint.setStyleSheet("color: gray;")
        layout.addWidget(self.preset_hint)

        layout.addWidget(QLabel("<b>Sensitivity</b>"))
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("Low"))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(voice_operations.get_sensitivity())
        self.slider.valueChanged.connect(self._sensitivity_changed)
        slider_row.addWidget(self.slider, 1)
        slider_row.addWidget(QLabel("High"))
        self.slider_value = QLabel()
        self.slider_value.setMinimumWidth(30)
        self.slider_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        slider_row.addWidget(self.slider_value)
        layout.addLayout(slider_row)
        explain = QLabel("Higher picks up quieter voices but also more background noise. "
                         "Lower ignores noise but you need to speak up.")
        explain.setWordWrap(True)
        explain.setStyleSheet("color: gray;")
        layout.addWidget(explain)

        layout.addWidget(QLabel("<b>Speed or accuracy</b>"))
        self.quality_box = QComboBox()
        self.quality_box.setAccessibleName("Speech recognition speed or accuracy")
        for label, _model, tip in voice_operations.QUALITY_OPTIONS:
            self.quality_box.addItem(label, label)
            self.quality_box.setItemData(self.quality_box.count() - 1, tip, Qt.ToolTipRole)
        self.quality_box.setCurrentIndex(max(0, self.quality_box.findData(voice_operations.get_quality())))
        self.quality_box.currentIndexChanged.connect(self._quality_changed)
        layout.addWidget(self.quality_box)
        self.quality_hint = QLabel()
        self.quality_hint.setWordWrap(True)
        self.quality_hint.setStyleSheet("color: gray;")
        layout.addWidget(self.quality_hint)
        self._update_quality_hint()

        test_label = QLabel("<b>Test it:</b> talk normally. The bar should turn green and pass the dashed line.")
        test_label.setWordWrap(True)
        layout.addWidget(test_label)
        self.meter = LevelMeter()
        layout.addWidget(self.meter)
        self.meter_status = QLabel()
        self.meter_status.setWordWrap(True)
        self.meter_status.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.meter_status.setMinimumHeight(self.meter_status.fontMetrics().lineSpacing() * 3)
        layout.addWidget(self.meter_status)

        close_btn = QPushButton("Done")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
        close_btn.setFocus()

        self._peak = 0
        self._device_note = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._sensitivity_changed(self.slider.value())

    def _sensitivity_changed(self, value):
        voice_operations.set_sensitivity(value)
        self.settings.setValue("mic_sensitivity", value)
        self.slider_value.setText(str(value))
        hint = "Custom setting."
        for preset_value, btn in self.preset_buttons.items():
            btn.setChecked(preset_value == value)
            if preset_value == value:
                hint = btn.toolTip()
        self.preset_hint.setText(hint)

    def _update_quality_hint(self):
        label = self.quality_box.currentData()
        tip = next(t for l, _m, t in voice_operations.QUALITY_OPTIONS if l == label)
        self.quality_hint.setText(tip)

    def _quality_changed(self, _index):
        label = self.quality_box.currentData()
        voice_operations.set_quality(label)
        self.settings.setValue("dictation_quality", label)
        self._update_quality_hint()
        if voice_operations.is_voice_active():
            self.quality_hint.setText(self.quality_hint.text() + " Takes effect next time you start dictation.")
        voice_operations.preload_model()

    def _device_changed(self, _index):
        name = self.device_box.currentData() or ""
        voice_operations.set_device(name)
        self.settings.setValue("mic_device", name)
        self._device_note = voice_operations.is_voice_active()
        if not self._device_note:
            self.monitor.start(name)

    def _tick(self):
        dictating = voice_operations.is_voice_active()
        if dictating:
            if self.monitor.running:
                self.monitor.stop()
            level = voice_operations.latest_level
        else:
            self._device_note = False
            if not self.monitor.running and not self.monitor.error:
                self.monitor.start(voice_operations.get_device())
            level = self.monitor.level
        trigger = voice_operations.trigger_level()
        self.meter.set_values(level, trigger)

        self._peak = max(level, self._peak - 2)
        if self.monitor.error and not dictating:
            msg = self.monitor.error
        elif self._peak >= trigger:
            msg = "SharkPad can hear you."
        elif self._peak >= trigger - 15:
            msg = "Almost. Speak a little louder, or move the slider toward High."
        else:
            msg = ("Not hearing speech yet. If you're talking, move the slider toward High "
                   "or pick a different microphone above.")
        if self._device_note:
            msg += "\nThe new microphone will be used the next time you start dictation."
        self.meter_status.setText(msg)

    def showEvent(self, event):
        super().showEvent(event)
        h = self.layout().heightForWidth(self.width())
        if h > 0:
            self.setFixedHeight(h)
        self.monitor.error = ""
        self.timer.start(50)

    def hideEvent(self, event):
        self.timer.stop()
        self.monitor.stop()
        super().hideEvent(event)

def load_dyslexia_fonts():
    regular_path = resource_path("OpenDyslexic-Regular.ttf")
    bold_path = resource_path("OpenDyslexic-Bold.ttf")
    regular_id = QFontDatabase.addApplicationFont(regular_path)
    bold_id = QFontDatabase.addApplicationFont(bold_path)
    regular_family = QFontDatabase.applicationFontFamilies(regular_id)[0] if regular_id != -1 else "Arial"
    bold_family = QFontDatabase.applicationFontFamilies(bold_id)[0] if bold_id != -1 else "Arial"
    return regular_family, bold_family

class SharkPadWindow(QMainWindow):
    """Main window that asks about unsaved changes before closing."""

    def __init__(self):
        super().__init__()
        self.close_guard = None

    def closeEvent(self, event):
        if self.close_guard and not self.close_guard():
            event.ignore()
            return
        super().closeEvent(event)


app = QApplication(sys.argv)
app.setApplicationName("SharkPad")
app.setOrganizationName("SharkPadApp")
dyslexia_regular_family, dyslexia_bold_family = load_dyslexia_fonts()
splash = SplashScreen(width=600, height=300)
splash.show_splash()

DEFAULT_FONT_SIZE = 14
TEXT_SPACING = {"Normal": (0.0, 0.0), "Wide": (1.5, 4.0), "Extra Wide": (3.0, 8.0)}
OPEN_FILTER = "SharkPad Notes (*_notes.txt *_notes.md *_notes.html);;Text Files (*.txt *.md *.html);;All Files (*)"
NOTE_TYPE_LABELS = {".txt": ".txt  (plain text)", ".md": ".md  (Markdown)", ".html": ".html  (web page)"}
IMAGE_TYPE_LABELS = {".png": ".png  (best quality, stays editable)", ".jpg": ".jpg  (smaller file, stays editable)",
                     ".bmp": ".bmp  (reopens as a flat picture)", ".webp": ".webp  (reopens as a flat picture)",
                     ".tiff": ".tiff  (reopens as a flat picture)"}
AI_HEADER = "AI Teacher explanation:\n"


def init_main():
    window = SharkPadWindow()
    window.resize(1000, 650)
    window.setWindowIcon(QIcon(resource_path("shark_pad_icon.ico")))

    settings = QSettings("SharkPadApp", "Settings")

    def setting_bool(key, default):
        return str(settings.value(key, default)).lower() == "true"

    central_widget = QWidget()
    main_layout = QHBoxLayout(central_widget)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    editor_area = QWidget()
    editor_layout = QVBoxLayout(editor_area)
    editor_layout.setContentsMargins(0, 0, 0, 0)
    editor_layout.setSpacing(0)

    notes_header = QWidget()
    notes_header_row = QHBoxLayout(notes_header)
    notes_header_row.setContentsMargins(8, 5, 8, 5)
    notes_title = QLabel("Notes")
    notes_title.setStyleSheet("font-weight: bold; font-size: 14px;")
    notes_header_row.addWidget(notes_title)
    notes_header_row.addStretch()
    notes_autosave = edit_operations.AutosaveToggle("notes")
    notes_header_row.addWidget(notes_autosave)
    editor_layout.addWidget(notes_header)

    editor = edit_operations.NotesEditor()
    editor.setPlaceholderText("Welcome to SharkPad. Start writing… (Press F1 for help)")
    editor.setAccessibleName("Notes")
    editor.setAccessibleDescription("Type your notes here")
    editor_layout.addWidget(editor)

    edit_operations.LetterUndo(editor)
    find_bar = edit_operations.FindBar(editor)
    editor_layout.addWidget(find_bar)
    main_layout.addWidget(editor_area, 1)

    drawing_pad = drawing_operations.create_drawing_pad()
    drawing_pad.setAccessibleName("Drawing pad")
    drawing_pad.setVisible(setting_bool("drawing_pad_visible", True))
    canvas = drawing_pad.canvas
    main_layout.addWidget(drawing_pad)

    window.setCentralWidget(central_widget)
    menu_bar = window.menuBar()
    status_bar = window.statusBar()

    current_file = [None]
    mic_dialog = [None]
    help_windows = {}
    state = {"listening": False, "thinking": False, "focus_mode": False, "pad_before_focus": True}

    try:
        voice_operations.set_sensitivity(int(settings.value("mic_sensitivity", voice_operations.DEFAULT_SENSITIVITY)))
    except (TypeError, ValueError):
        voice_operations.set_sensitivity(voice_operations.DEFAULT_SENSITIVITY)
    voice_operations.set_device(settings.value("mic_device", "") or "")
    voice_operations.set_quality(settings.value("dictation_quality", voice_operations.DEFAULT_QUALITY))

    saved_token = settings.value("api_key")
    if saved_token:
        summarization_operations.set_api_token(saved_token)

    current_theme = [settings.value("theme", "Light")]
    if current_theme[0] not in preferences_operations.THEMES:
        current_theme[0] = "Light"
    preferences_operations.apply_theme(editor, current_theme[0])

    show_hints = [setting_bool("show_shortcut_hints", True)]

    def bind(keys, callback):
        for k in keys:
            QShortcut(QKeySequence(k), window, callback)

    def add_action(menu, text, callback, checkable=False, checked=False):
        action = QAction(text, window, checkable=checkable)
        if checkable:
            action.setChecked(checked)
            action.toggled.connect(callback)
        else:
            action.triggered.connect(callback)
        menu.addAction(action)
        return action

    def is_dirty():
        return editor.document().isModified() or canvas.modified

    def display_name():
        if not current_file[0]:
            return "Untitled"
        if project_operations.is_project_notes(current_file[0]):
            return project_operations.split_project(current_file[0])[1]
        return os.path.basename(current_file[0])

    def update_title():
        name = display_name()
        extra = ""
        if state["thinking"]:
            extra = " - AI Teacher is thinking..."
        elif state["listening"]:
            extra = " - listening"
        window.setWindowTitle(f"{name}[*] - SharkPad{extra}")
        window.setWindowModified(is_dirty())

    editor.document().modificationChanged.connect(lambda _: update_title())
    canvas.changed.connect(update_title)

    try:
        start_size = int(settings.value("font_size", DEFAULT_FONT_SIZE))
    except (TypeError, ValueError):
        start_size = DEFAULT_FONT_SIZE
    font_state = {
        "size": max(6, min(96, start_size)),
        "dyslexia": settings.value("dyslexia_font", "Off"),
        "spacing": settings.value("text_spacing", "Normal"),
    }
    font_size_indicator = QAction("", window)
    font_size_indicator.setDisabled(True)

    def apply_editor_font():
        mode = font_state["dyslexia"]
        family = {"Regular": dyslexia_regular_family, "Bold": dyslexia_bold_family}.get(mode, "Arial")
        f = QFont(family, font_state["size"])
        f.setBold(mode == "Bold")
        letter, word = TEXT_SPACING.get(font_state["spacing"], (0.0, 0.0))
        f.setLetterSpacing(QFont.AbsoluteSpacing, letter)
        f.setWordSpacing(word)
        editor.setFont(f)
        font_size_indicator.setText(f"Font Size: {font_state['size']}")
        settings.setValue("font_size", font_state["size"])
        settings.setValue("dyslexia_font", mode)
        settings.setValue("text_spacing", font_state["spacing"])

    def set_font_size(size):
        font_state["size"] = max(6, min(96, size))
        apply_editor_font()
        status_bar.showMessage(f"Text size: {font_state['size']}", 1500)

    def zoom(delta):
        set_font_size(font_state["size"] + delta)

    wheel_zoom = edit_operations.CtrlWheelZoom(zoom, editor)
    editor.viewport().installEventFilter(wheel_zoom)
    apply_editor_font()

    stats_label = QLabel()
    stats_label.setAccessibleName("Document statistics")
    status_bar.addPermanentWidget(stats_label)
    restore_btn = QPushButton("Restore original text")
    restore_btn.setToolTip("Bring back your notes as they were before the AI Teacher explanation")
    restore_btn.hide()
    status_bar.addPermanentWidget(restore_btn)

    stats_timer = QTimer(window)
    stats_timer.setSingleShot(True)
    stats_timer.setInterval(150)
    stats_timer.timeout.connect(lambda: stats_label.setText(edit_operations.text_stats(editor)))
    editor.textChanged.connect(stats_timer.start)
    editor.cursorPositionChanged.connect(stats_timer.start)
    editor.selectionChanged.connect(stats_timer.start)
    stats_timer.start()

    ai_state = {"before": None, "after": None, "range": None, "doc_at_start": None}
    restore_action = QAction("Restore Original Text", window)
    restore_action.setEnabled(False)

    def clear_ai_restore():
        ai_state["before"] = ai_state["after"] = None
        restore_action.setEnabled(False)
        restore_btn.hide()

    recent_menu = QMenu("Open Recent", window)

    def recent_files():
        value = settings.value("recent_files", [])
        if isinstance(value, str):
            value = [value]
        return [p for p in (value or []) if isinstance(p, str)]

    def rebuild_recent_menu():
        recent_menu.clear()
        files = [p for p in recent_files() if os.path.exists(p)]
        if not files:
            empty = recent_menu.addAction("No recent notes")
            empty.setEnabled(False)
            return
        for i, path in enumerate(files):
            label = f"&{i + 1}  {os.path.basename(path)}" if i < 9 else os.path.basename(path)
            a = recent_menu.addAction(label)
            a.setToolTip(path)
            a.triggered.connect(lambda _=False, p=path: open_note(p))
        recent_menu.addSeparator()
        recent_menu.addAction("Clear List", lambda: (settings.setValue("recent_files", []), rebuild_recent_menu()))

    def add_recent(path):
        files = [path] + [p for p in recent_files() if os.path.normcase(p) != os.path.normcase(path)]
        settings.setValue("recent_files", files[:8])
        rebuild_recent_menu()

    def notes_ext():
        ext = settings.value("notes_ext", ".txt")
        return ext if ext in project_operations.NOTE_EXTENSIONS else ".txt"

    def image_ext():
        allowed = project_operations.image_extensions()
        ext = settings.value("image_ext", ".png")
        return ext if ext in allowed else (allowed[0] if allowed else ".png")

    def current_project():
        if current_file[0] and project_operations.is_project_notes(current_file[0]):
            return project_operations.split_project(current_file[0])
        return None

    def saved_stamp():
        return "Saved " + time.strftime("%I:%M %p").lstrip("0")

    def write_project(folder, name, notes=True, image=True, force=False):
        notes_file = project_operations.notes_path(folder, name, notes_ext())
        image_file = project_operations.image_path(folder, name, image_ext())
        try:
            os.makedirs(folder, exist_ok=True)
            if notes:
                if force or editor.document().isModified() or not os.path.exists(notes_file):
                    project_operations.write_notes(notes_file, editor.toPlainText(), name)
                project_operations.remove_other_versions(folder, name, notes_file)
                editor.document().setModified(False)
            if image:
                if drawing_pad.has_drawing():
                    if force or canvas.modified or not os.path.exists(image_file):
                        project_operations.write_image(drawing_pad, image_file)
                    project_operations.remove_other_versions(folder, name, image_file, images=True)
                else:
                    project_operations.remove_other_versions(folder, name, None, images=True)
                canvas.modified = False
                canvas.changed.emit()
        except OSError as e:
            QMessageBox.critical(window, "Couldn't Save", f"Could not save to {folder}:\n{e}")
            return False
        if notes:
            recovery_operations.clear()
            if os.path.normcase(notes_file) != os.path.normcase(current_file[0] or ""):
                current_file[0] = notes_file
                add_recent(notes_file)
        for box, saved in ((notes_autosave, notes), (drawing_pad.autosave, image)):
            if saved and box.isChecked():
                box.set_status(saved_stamp())
        update_title()
        return True

    def save_as():
        project = current_project()
        if project:
            start_dir, suggested = os.path.dirname(project[0]), project[1]
        else:
            start_dir = os.path.join(os.path.expanduser("~"), "Documents")
            suggested = project_operations.clean_name(current_file[0]) if current_file[0] else "My Notes"
        chosen, _ = QFileDialog.getSaveFileName(
            window, "Save - name your notes (they go in a folder with this name)",
            os.path.join(start_dir, suggested), "SharkPad folder (*)",
            options=QFileDialog.DontConfirmOverwrite)
        if not chosen:
            return False
        folder, name = project_operations.project_from_choice(chosen)
        same_project = bool(project) and os.path.normcase(folder) == os.path.normcase(project[0]) and name == project[1]
        if not same_project and project_operations.existing_files(folder, name):
            reply = QMessageBox.question(
                window, "Replace Saved Notes?",
                f"\"{name}\" already has saved notes in:\n{folder}\n\nReplace them?")
            if reply != QMessageBox.Yes:
                return False
        if not write_project(folder, name, force=True):
            return False
        status_bar.showMessage(f"Saved \"{name}\" in {folder}", 4000)
        return True

    def save():
        project = current_project()
        if not project:
            return save_as()
        if not write_project(*project):
            return False
        status_bar.showMessage(f"Saved \"{project[1]}\"", 3000)
        return True

    def maybe_save():
        """Ask to save unsaved work. Returns False if the user cancels."""
        if not is_dirty():
            return True
        name = display_name() if current_file[0] else "this note"
        box = QMessageBox(QMessageBox.Warning, "Unsaved Changes",
                          f"Do you want to save your changes to {name}?",
                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, window)
        box.setInformativeText("If you don't save, your changes will be lost.")
        box.setDefaultButton(QMessageBox.Save)
        reply = box.exec()
        if reply == QMessageBox.Save:
            return save()
        return reply == QMessageBox.Discard

    def reset_document():
        clear_ai_restore()
        recovery_operations.clear()
        update_title()

    def new_note():
        if not maybe_save():
            return
        read_aloud.stop()
        editor.clear()
        canvas.clear_canvas()
        editor.document().setModified(False)
        current_file[0] = None
        reset_document()

    def open_note(path=None):
        if not maybe_save():
            return
        if not path:
            start = os.path.dirname(current_file[0]) if current_file[0] else ""
            path, _ = QFileDialog.getOpenFileName(window, "Open Notes", start, OPEN_FILTER)
        if not path:
            return
        try:
            text = project_operations.read_notes(path)
        except OSError as e:
            QMessageBox.critical(window, "Couldn't Open", f"Could not open the file:\n{e}")
            settings.setValue("recent_files", [p for p in recent_files() if p != path])
            rebuild_recent_menu()
            return
        read_aloud.stop()
        editor.setPlainText(text)
        editor.document().setModified(False)
        image_file = project_operations.find_image(path)
        if image_file:
            drawing_pad.load_drawing(image_file)
        else:
            canvas.clear_canvas()
        current_file[0] = path
        add_recent(path)
        reset_document()
        for box in (notes_autosave, drawing_pad.autosave):
            box.set_status(saved_stamp() if box.isChecked() and current_project() else "")
        status_bar.showMessage(f"Opened \"{display_name()}\"", 3000)

    autosave_timers = {}

    def autosave(notes):
        box = notes_autosave if notes else drawing_pad.autosave
        project = current_project()
        if not box.isChecked() or not project:
            return
        changed = editor.document().isModified() if notes else canvas.modified
        if changed:
            write_project(*project, notes=notes, image=not notes)

    def content_changed(notes):
        box = notes_autosave if notes else drawing_pad.autosave
        if not box.isChecked():
            return
        if not current_project():
            box.set_status("Save once (Ctrl+S) to start")
            return
        if editor.document().isModified() if notes else canvas.modified:
            box.set_status("Editing...")
            autosave_timers[notes].start()

    def toggle_autosave(notes, on):
        box = notes_autosave if notes else drawing_pad.autosave
        settings.setValue("autosave_notes" if notes else "autosave_drawing", on)
        if not on:
            autosave_timers[notes].stop()
            box.set_status("")
            return
        if not current_project() and not save_as():
            box.setChecked(False)
            settings.setValue("autosave_notes" if notes else "autosave_drawing", False)
            return
        autosave(notes)
        box.set_status(saved_stamp())

    for is_notes, box, key in ((True, notes_autosave, "autosave_notes"), (False, drawing_pad.autosave, "autosave_drawing")):
        timer = QTimer(window)
        timer.setSingleShot(True)
        timer.setInterval(1500)
        timer.timeout.connect(lambda n=is_notes: autosave(n))
        autosave_timers[is_notes] = timer
        box.setChecked(setting_bool(key, False))
        box.toggled.connect(lambda on, n=is_notes: toggle_autosave(n, on))
    editor.textChanged.connect(lambda: content_changed(True))
    canvas.changed.connect(lambda: content_changed(False))

    def print_note():
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, window)
        if dialog.exec() == QDialog.Accepted:
            editor.document().print_(printer)

    def export_pdf():
        from PySide6.QtPrintSupport import QPrinter
        default = os.path.splitext(current_file[0])[0] + ".pdf" if current_file[0] else "Notes.pdf"
        path, _ = QFileDialog.getSaveFileName(window, "Export as PDF", default, "PDF Files (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        editor.document().print_(printer)
        status_bar.showMessage(f"Exported {os.path.basename(path)}", 3000)

    file_menu = menu_bar.addMenu("&File")
    add_action(file_menu, "New (Ctrl+N)", new_note)
    add_action(file_menu, "Open (Ctrl+O)", lambda: open_note())
    file_menu.addMenu(recent_menu)
    rebuild_recent_menu()
    file_menu.addSeparator()
    add_action(file_menu, "Save (Ctrl+S)", save)
    add_action(file_menu, "Save As (Ctrl+Shift+S)", save_as)
    file_menu.addSeparator()
    add_action(file_menu, "Export as PDF...", export_pdf)
    add_action(file_menu, "Print (Ctrl+P)", print_note)
    file_menu.addSeparator()
    add_action(file_menu, "Exit (Ctrl+Q)", window.close)

    def canvas_focused():
        return QApplication.focusWidget() is canvas

    def undo():
        if canvas_focused():
            if not canvas.undo():
                status_bar.showMessage("Nothing to undo on the drawing pad.", 2000)
        else:
            editor.undo()

    def redo():
        if canvas_focused():
            if not canvas.redo():
                status_bar.showMessage("Nothing to redo on the drawing pad.", 2000)
        else:
            editor.redo()

    def find_next(backward=False):
        if not find_bar.find_edit.text():
            find_bar.open()
        else:
            find_bar.show()
            find_bar.find_next(backward=backward)

    edit_menu = menu_bar.addMenu("&Edit")
    add_action(edit_menu, "Undo (Ctrl+Z)", undo)
    add_action(edit_menu, "Redo (Ctrl+Shift+Z)", redo)
    edit_menu.addSeparator()
    add_action(edit_menu, "Cut (Ctrl+X)", editor.cut)
    add_action(edit_menu, "Copy (Ctrl+C)", editor.copy)
    add_action(edit_menu, "Paste (Ctrl+V)", editor.paste)
    add_action(edit_menu, "Select All (Ctrl+A)", editor.selectAll)
    edit_menu.addSeparator()
    add_action(edit_menu, "Find (Ctrl+F)", lambda: find_bar.open())
    add_action(edit_menu, "Find Next (F3)", lambda: find_next())
    add_action(edit_menu, "Find Previous (Shift+F3)", lambda: find_next(backward=True))
    add_action(edit_menu, "Replace (Ctrl+H)", lambda: find_bar.open(replace=True))
    edit_menu.addSeparator()
    add_action(edit_menu, "Duplicate Line (Ctrl+D)", lambda: edit_operations.duplicate_line(editor))
    add_action(edit_menu, "Move Line Up (Alt+Up)", lambda: edit_operations.move_lines(editor, up=True))
    add_action(edit_menu, "Move Line Down (Alt+Down)", lambda: edit_operations.move_lines(editor, up=False))
    add_action(edit_menu, "Insert Date and Time (F5)", lambda: edit_operations.insert_date_time(editor))
    edit_menu.addSeparator()

    def set_spell_check(on):
        settings.setValue("spell_check", on)
        ai_operations.set_spellcheck_enabled(editor, on)

    spell_on = setting_bool("spell_check", True)
    editor.spellcheck_enabled = spell_on
    add_action(edit_menu, "Check Spelling", set_spell_check, checkable=True, checked=spell_on)

    autocorrector = ai_operations.AutoCorrector(editor)
    autocorrector.enabled = setting_bool("autocorrect", True)
    autocorrector.corrected.connect(lambda typed, fix: status_bar.showMessage(
        f"Autocorrected \"{typed}\" to \"{fix}\"  (Ctrl+Z puts it back)", 4000))
    autocorrector.rejected.connect(lambda typed: status_bar.showMessage(
        f"Got it, \"{typed}\" won't be autocorrected again.", 4000))

    def set_autocorrect(on):
        autocorrector.enabled = on
        settings.setValue("autocorrect", on)

    add_action(edit_menu, "Autocorrect While Typing", set_autocorrect, checkable=True, checked=autocorrector.enabled)

    view_menu = menu_bar.addMenu("&View")

    def set_word_wrap(on):
        editor.setLineWrapMode(QPlainTextEdit.WidgetWidth if on else QPlainTextEdit.NoWrap)
        settings.setValue("word_wrap", on)

    wrap_on = setting_bool("word_wrap", True)
    set_word_wrap(wrap_on)
    add_action(view_menu, "Word Wrap", set_word_wrap, checkable=True, checked=wrap_on)

    def set_line_numbers(on):
        editor.set_line_numbers(on)
        settings.setValue("line_numbers", on)

    numbers_on = setting_bool("line_numbers", True)
    editor.set_line_numbers(numbers_on)
    add_action(view_menu, "Line Numbers", set_line_numbers, checkable=True, checked=numbers_on)
    view_menu.addSeparator()
    add_action(view_menu, "Zoom In (Ctrl+=)", lambda: zoom(2))
    add_action(view_menu, "Zoom Out (Ctrl+-)", lambda: zoom(-2))
    add_action(view_menu, "Reset Zoom (Ctrl+0)", lambda: set_font_size(DEFAULT_FONT_SIZE))

    def ask_font_size():
        size, ok = QInputDialog.getInt(window, "Font Size", "Text size:", font_state["size"], 6, 96)
        if ok:
            set_font_size(size)

    add_action(view_menu, "Set Font Size...", ask_font_size)
    view_menu.addAction(font_size_indicator)
    view_menu.addSeparator()

    def show_drawing_pad(on):
        drawing_pad.setVisible(on)
        settings.setValue("drawing_pad_visible", on)

    add_action(view_menu, "Show Drawing Pad", show_drawing_pad,
               checkable=True, checked=drawing_pad.isVisible())

    def toggle_focus_mode():
        if not state["focus_mode"]:
            state["pad_before_focus"] = drawing_pad.isVisible()
            drawing_pad.setVisible(False)
            window.showFullScreen()
            status_bar.showMessage("Focus Mode: press F11 or Esc to leave.", 4000)
        else:
            drawing_pad.setVisible(state["pad_before_focus"])
            window.showNormal()
        state["focus_mode"] = not state["focus_mode"]
        focus_action.setChecked(state["focus_mode"])

    focus_action = QAction("Focus Mode (F11)", window, checkable=True)
    focus_action.triggered.connect(lambda _: toggle_focus_mode())
    view_menu.addAction(focus_action)

    access_menu = menu_bar.addMenu("&Accessibility")
    read_aloud = accessibility_operations.ReadAloud(editor)
    rate_name = settings.value("tts_rate", "Normal")
    read_aloud.set_rate(dict(accessibility_operations.READING_RATES).get(rate_name, 0.0))
    read_aloud.set_voice(settings.value("tts_voice", "") or "")

    read_action = add_action(access_menu, "Read Aloud (Ctrl+Shift+R)", read_aloud.toggle)
    read_aloud.error.connect(lambda msg: QMessageBox.information(window, "Read Aloud", msg))

    def reading_changed(on):
        preferences_operations.set_hinted_text(
            read_action, "Stop Reading (Ctrl+Shift+R)" if on else "Read Aloud (Ctrl+Shift+R)", show_hints[0])
        if on:
            status_bar.showMessage("Reading aloud... press Esc or Ctrl+Shift+R to stop.")
        else:
            status_bar.clearMessage()

    read_aloud.speaking_changed.connect(reading_changed)

    speed_menu = access_menu.addMenu("Reading Speed")
    speed_group = QActionGroup(window)
    for label, rate in accessibility_operations.READING_RATES:
        a = speed_menu.addAction(label)
        a.setCheckable(True)
        a.setChecked(label == rate_name)
        speed_group.addAction(a)
        a.triggered.connect(lambda _=False, l=label, r=rate: (read_aloud.set_rate(r), settings.setValue("tts_rate", l)))

    voice_menu = access_menu.addMenu("Voice")

    def fill_voice_menu():
        voice_menu.clear()
        voices = read_aloud.voices()
        if not voices:
            none = voice_menu.addAction("No voices installed (see Help > Accessibility)")
            none.setEnabled(False)
            return
        group = QActionGroup(voice_menu)
        current = settings.value("tts_voice", "") or ""
        for name in [""] + voices:
            a = voice_menu.addAction(name or "System default")
            a.setCheckable(True)
            a.setChecked(name == current)
            group.addAction(a)
            a.triggered.connect(lambda _=False, n=name: (read_aloud.set_voice(n), settings.setValue("tts_voice", n)))

    voice_menu.aboutToShow.connect(fill_voice_menu)
    access_menu.addSeparator()

    dyslexia_menu = access_menu.addMenu("Dyslexia Font")
    dyslexia_group = QActionGroup(window)
    for mode in ["Off", "Regular", "Bold"]:
        a = dyslexia_menu.addAction(mode)
        a.setCheckable(True)
        a.setChecked(font_state["dyslexia"] == mode)
        dyslexia_group.addAction(a)
        a.triggered.connect(lambda _=False, m=mode: (font_state.update(dyslexia=m), apply_editor_font()))

    spacing_menu = access_menu.addMenu("Text Spacing")
    spacing_group = QActionGroup(window)
    for name in TEXT_SPACING:
        a = spacing_menu.addAction(name)
        a.setCheckable(True)
        a.setChecked(font_state["spacing"] == name)
        spacing_group.addAction(a)
        a.triggered.connect(lambda _=False, n=name: (font_state.update(spacing=n), apply_editor_font()))

    guide_on = [setting_bool("reading_guide", False)]

    def set_reading_guide(on):
        guide_on[0] = on
        settings.setValue("reading_guide", on)
        edit_operations.update_reading_guide(editor, on)

    editor.cursorPositionChanged.connect(lambda: edit_operations.update_reading_guide(editor, guide_on[0]))
    add_action(access_menu, "Reading Guide (highlight current line)", set_reading_guide,
               checkable=True, checked=guide_on[0])
    edit_operations.update_reading_guide(editor, guide_on[0])

    def set_thick_cursor(on):
        editor.setCursorWidth(3 if on else 1)
        settings.setValue("thick_cursor", on)

    thick = setting_bool("thick_cursor", False)
    set_thick_cursor(thick)
    add_action(access_menu, "Thick Text Cursor", set_thick_cursor, checkable=True, checked=thick)
    access_menu.addSeparator()

    def apply_and_save_theme(t):
        preferences_operations.apply_theme(editor, t)
        settings.setValue("theme", t)
        current_theme[0] = t
        for a in theme_group.actions():
            a.setChecked(a.text() == t)
        high_contrast_action.blockSignals(True)
        high_contrast_action.setChecked(t == "High Contrast")
        high_contrast_action.blockSignals(False)
        edit_operations.update_reading_guide(editor, guide_on[0])

    previous_theme = [current_theme[0] if current_theme[0] != "High Contrast" else "Light"]

    def toggle_high_contrast(on):
        if on:
            previous_theme[0] = current_theme[0]
            apply_and_save_theme("High Contrast")
        else:
            apply_and_save_theme(previous_theme[0] if previous_theme[0] != "High Contrast" else "Light")

    high_contrast_action = add_action(access_menu, "High Contrast Colors", toggle_high_contrast,
                                      checkable=True, checked=current_theme[0] == "High Contrast")

    preferences_menu = menu_bar.addMenu("&Preferences")
    themes_menu = QMenu("Color Scheme", window)
    theme_group = QActionGroup(window)
    for theme in preferences_operations.THEMES:
        a = themes_menu.addAction(theme)
        a.setCheckable(True)
        a.setChecked(theme == current_theme[0])
        theme_group.addAction(a)
        a.triggered.connect(lambda _=False, t=theme: apply_and_save_theme(t))
    preferences_menu.addMenu(themes_menu)

    file_types_menu = preferences_menu.addMenu("Save File Types")
    for title, key, choices, labels, current in (
            ("Notes", "notes_ext", project_operations.NOTE_EXTENSIONS, NOTE_TYPE_LABELS, notes_ext()),
            ("Drawing", "image_ext", project_operations.image_extensions(), IMAGE_TYPE_LABELS, image_ext())):
        submenu = file_types_menu.addMenu(title)
        group = QActionGroup(submenu)
        for ext in choices:
            a = submenu.addAction(labels.get(ext, ext))
            a.setCheckable(True)
            a.setChecked(ext == current)
            group.addAction(a)
            a.triggered.connect(lambda _=False, k=key, e=ext, t=title: (
                settings.setValue(k, e),
                status_bar.showMessage(f"{t} will be saved as {e} from now on.", 4000)))

    def toggle_shortcut_hints(checked):
        show_hints[0] = checked
        settings.setValue("show_shortcut_hints", checked)
        preferences_operations.apply_shortcut_hints(window, checked)

    add_action(preferences_menu, "Show Shortcut Hints", toggle_shortcut_hints, checkable=True, checked=show_hints[0])

    ai_menu = menu_bar.addMenu("AI &Tools")
    add_action(ai_menu, "AI Teacher Settings (Token)...", lambda: OpenAISettingsDialog(window).exec())
    ai_menu.addSeparator()

    voice_action = QAction("Voice Dictation (Ctrl+Shift+V)", window)

    def set_voice_ui(is_on):
        state["listening"] = is_on
        preferences_operations.set_hinted_text(
            voice_action,
            "Stop Dictation (Ctrl+Shift+V)" if is_on else "Voice Dictation (Ctrl+Shift+V)",
            show_hints[0],
        )
        update_title()

    def voice_status(msg):
        status_bar.showMessage(f"Dictation: {msg}")

    def voice_error(msg):
        status_bar.clearMessage()
        QMessageBox.warning(window, "Voice Dictation", msg)

    def voice_stopped():
        set_voice_ui(voice_operations.is_voice_active())
        if not voice_operations.is_voice_active():
            status_bar.showMessage("Dictation stopped.", 3000)

    def toggle_voice_ui():
        is_on = voice_operations.toggle_voice(editor, voice_status, voice_error, voice_stopped)
        set_voice_ui(is_on)
        if is_on:
            settings.setValue("dictation_used", True)
        else:
            status_bar.showMessage("Dictation stopped.", 3000)

    voice_action.triggered.connect(toggle_voice_ui)
    ai_menu.addAction(voice_action)

    def show_mic_settings():
        if not mic_dialog[0]:
            mic_dialog[0] = VoiceSettingsDialog(window, settings)
        mic_dialog[0].show()
        mic_dialog[0].raise_()
        mic_dialog[0].activateWindow()

    add_action(ai_menu, "Voice Dictation Settings...", show_mic_settings)
    ai_menu.addSeparator()

    app.aboutToQuit.connect(voice_operations.wait_for_shutdown)

    summarize_action = QAction("AI Teacher Explain (Ctrl+Shift+T)", window)

    def explain():
        if summarization_operations.is_busy():
            status_bar.showMessage("The AI Teacher is still working on the last explanation...", 3000)
            return
        text = editor.toPlainText()
        c = editor.textCursor()
        start, end = (c.selectionStart(), c.selectionEnd()) if c.hasSelection() else (0, len(text))
        chunk = text[start:end]
        if not chunk.strip():
            QMessageBox.information(window, "No Text", "Please write or select some notes for me to explain!")
            return
        ai_state.update(range=(start, end), doc_at_start=text)
        state["thinking"] = True
        summarize_action.setEnabled(False)
        update_title()
        status_bar.showMessage("AI Teacher is thinking... you can keep working.")
        summarization_operations.explain_async(chunk, on_explained)

    def on_explained(ok, result):
        state["thinking"] = False
        summarize_action.setEnabled(True)
        update_title()
        if not ok:
            status_bar.clearMessage()
            QMessageBox.warning(window, "AI Teacher", result)
            return
        before = editor.toPlainText()
        start, end = ai_state["range"]
        if before != ai_state["doc_at_start"]:
            edit_operations.replace_range(editor, len(before), len(before), "\n\n" + AI_HEADER + result)
        elif keep_notes_action.isChecked():
            edit_operations.replace_range(editor, end, end, "\n\n" + AI_HEADER + result)
        else:
            edit_operations.replace_range(editor, start, end, result)
        ai_state["before"] = before
        ai_state["after"] = editor.toPlainText()
        restore_action.setEnabled(True)
        restore_btn.show()
        status_bar.showMessage("Explanation added. Ctrl+Z or \"Restore original text\" brings back your notes.", 10000)

    def restore_original():
        if ai_state["before"] is None:
            return
        if editor.toPlainText() != ai_state["after"]:
            reply = QMessageBox.question(
                window, "Restore Original Text",
                "You've changed the text since the explanation was added. Restoring brings your notes back "
                "exactly as they were before the explanation, so those changes go too (Ctrl+Z can undo the restore).\n\n"
                "Restore anyway?")
            if reply != QMessageBox.Yes:
                return
        edit_operations.replace_all_text(editor, ai_state["before"])
        clear_ai_restore()
        status_bar.showMessage("Your original text is back.", 4000)

    summarize_action.triggered.connect(explain)
    ai_menu.addAction(summarize_action)
    keep_notes_action = add_action(
        ai_menu, "Keep My Notes (add explanation below)",
        lambda on: settings.setValue("ai_keep_notes", on),
        checkable=True, checked=setting_bool("ai_keep_notes", False))
    restore_action.triggered.connect(restore_original)
    ai_menu.addAction(restore_action)
    restore_btn.clicked.connect(restore_original)

    shortcut_groups = [
        ("Files", [("Ctrl+N", "New note"), ("Ctrl+O", "Open a note"), ("Ctrl+S", "Save"),
                   ("Ctrl+Shift+S", "Save As"), ("Ctrl+P", "Print"), ("Ctrl+Q", "Exit")]),
        ("Editing", [("Ctrl+Z", "Undo (text, or drawing when the pad is clicked)"),
                     ("Ctrl+Y or Ctrl+Shift+Z", "Redo"), ("Ctrl+X / Ctrl+C / Ctrl+V", "Cut / Copy / Paste"),
                     ("Ctrl+A", "Select all"), ("Ctrl+F", "Find"), ("F3 / Shift+F3", "Next / previous match"),
                     ("Ctrl+H", "Replace"), ("Ctrl+D", "Duplicate line"), ("Alt+Up / Alt+Down", "Move line up / down"),
                     ("F5", "Insert date and time")]),
        ("View", [("Ctrl+= / Ctrl+-", "Bigger / smaller text"), ("Ctrl + mouse wheel", "Bigger / smaller text"),
                  ("Ctrl+0", "Reset text size"), ("F11", "Focus Mode (full screen)")]),
        ("Accessibility", [("Ctrl+Shift+R", "Read aloud / stop reading"), ("Esc", "Stop reading, close find, or leave Focus Mode")]),
        ("AI Tools", [("Ctrl+Shift+V", "Voice dictation on / off"), ("Ctrl+Shift+T", "AI Teacher explain")]),
        ("Drawing Pad tools", [("Ctrl+Shift+A  or  V", "Select"), ("Ctrl+Shift+D  or  P", "Pen"),
                               ("Ctrl+Shift+H  or  H", "Highlighter"), ("Ctrl+Shift+E  or  E", "Eraser"),
                               ("Ctrl+Shift+X  or  T", "Text"), ("Ctrl+Shift+U", "Add an image"),
                               ("Ctrl+Shift+C", "Pick a color")]),
        ("Drawing Pad selection (click the pad first)", [
            ("Drag on empty space", "Select everything inside the box"), ("Shift+click", "Add or remove from selection"),
            ("Ctrl+A", "Select everything"), ("Arrow keys / Shift+arrows", "Nudge 1 / 10 pixels"),
            ("Delete or Backspace", "Delete the selection"), ("Ctrl+C / Ctrl+X / Ctrl+V", "Copy / cut / paste"),
            ("Ctrl+D", "Duplicate"), ("Ctrl+Shift+] / Ctrl+Shift+[", "To front / to back"),
            ("Ctrl+] / Ctrl+[", "Forward / backward one layer"), ("Double-click text", "Edit the text")]),
        ("Help", [("F1", "Keyboard shortcuts")]),
    ]

    def show_help(key, title, body):
        dlg = help_windows.get(key)
        if dlg is None:
            dlg = accessibility_operations.HelpDialog(window, title, body)
            help_windows[key] = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    help_menu = menu_bar.addMenu("&Help")
    add_action(help_menu, "Getting Started", lambda: show_help(
        "start", "Getting Started", accessibility_operations.GETTING_STARTED_HTML))
    add_action(help_menu, "Keyboard Shortcuts (F1)", lambda: show_help(
        "keys", "Keyboard Shortcuts", accessibility_operations.shortcuts_html(shortcut_groups)))
    add_action(help_menu, "Accessibility Features", lambda: show_help(
        "access", "Accessibility Features", accessibility_operations.ACCESSIBILITY_HTML))
    add_action(help_menu, "Voice Dictation Help", lambda: show_help(
        "voice", "Voice Dictation Help", accessibility_operations.DICTATION_HELP_HTML))
    help_menu.addSeparator()
    add_action(help_menu, "Report a Problem...", lambda: QDesktopServices.openUrl(
        QUrl("https://github.com/GabeyShark7/SharkPad/issues")))
    add_action(help_menu, "About SharkPad", lambda: show_help(
        "about", "About SharkPad", accessibility_operations.about_html()))

    explain_ctx = QAction("Explain with AI Teacher", window)
    explain_ctx.triggered.connect(explain)
    read_ctx = QAction("Read Aloud", window)
    read_ctx.triggered.connect(read_aloud.toggle)
    editor.extra_context_actions = [read_ctx, explain_ctx]

    def escape():
        if read_aloud.is_speaking():
            read_aloud.stop()
        elif find_bar.isVisible():
            find_bar.close_bar()
        elif state["focus_mode"]:
            toggle_focus_mode()

    bind(["Ctrl+N"], new_note)
    bind(["Ctrl+O"], lambda: open_note())
    bind(["Ctrl+S"], save)
    bind(["Ctrl+Shift+S"], save_as)
    bind(["Ctrl+P"], print_note)
    bind(["Ctrl+Q"], window.close)
    bind(["Ctrl+Z"], undo)
    bind(["Ctrl+Y", "Ctrl+Shift+Z"], redo)
    bind(["Ctrl+F"], lambda: find_bar.open())
    bind(["F3"], lambda: find_next())
    bind(["Shift+F3"], lambda: find_next(backward=True))
    bind(["Ctrl+H"], lambda: find_bar.open(replace=True))
    bind(["Ctrl+D"], lambda: edit_operations.duplicate_line(editor))
    bind(["Alt+Up"], lambda: edit_operations.move_lines(editor, up=True))
    bind(["Alt+Down"], lambda: edit_operations.move_lines(editor, up=False))
    bind(["F5"], lambda: edit_operations.insert_date_time(editor))
    bind(["Ctrl+=", "Ctrl++"], lambda: zoom(2))
    bind(["Ctrl+-"], lambda: zoom(-2))
    bind(["Ctrl+0"], lambda: set_font_size(DEFAULT_FONT_SIZE))
    bind(["F11", "Ctrl+Meta+F"] if sys.platform == "darwin" else ["F11"], toggle_focus_mode)
    bind(["F1"], lambda: show_help("keys", "Keyboard Shortcuts", accessibility_operations.shortcuts_html(shortcut_groups)))
    bind(["Ctrl+Shift+R"], read_aloud.toggle)
    bind(["Escape"], escape)
    bind(["Ctrl+Shift+V"], toggle_voice_ui)
    bind(["Ctrl+Shift+T"], explain)

    bind(["Ctrl+Shift+D"], lambda: drawing_pad.set_mode('draw'))
    bind(["Ctrl+Shift+E"], lambda: drawing_pad.set_mode('erase'))
    bind(["Ctrl+Shift+H"], lambda: drawing_pad.set_mode('highlight'))
    bind(["Ctrl+Shift+X"], lambda: drawing_pad.set_mode('text'))
    bind(["Ctrl+Shift+A"], lambda: drawing_pad.set_mode('select'))
    bind(["Ctrl+Shift+U"], drawing_pad.upload_image)
    bind(["Ctrl+Shift+C"], drawing_pad.pick_color)
    bind(["Ctrl+Shift+]", "Ctrl+}", "Ctrl+Shift+}"], drawing_pad.bring_to_front)
    bind(["Ctrl+Shift+[", "Ctrl+{", "Ctrl+Shift+{"], drawing_pad.send_to_back)
    bind(["Ctrl+]"], drawing_pad.bring_forward)
    bind(["Ctrl+["], drawing_pad.send_backward)
    bind(["Ctrl+Shift+Del"], drawing_pad.delete_image)

    preferences_operations.apply_shortcut_hints(window, show_hints[0])

    def before_close():
        for is_notes, timer in autosave_timers.items():
            if timer.isActive():
                timer.stop()
                autosave(is_notes)
        if not maybe_save():
            return False
        read_aloud.stop()
        recovery_operations.clear()
        return True

    window.close_guard = before_close

    def autosave_backup():
        if editor.document().isModified():
            recovery_operations.save(editor.toPlainText(), current_file[0])

    backup_timer = QTimer(window)
    backup_timer.timeout.connect(autosave_backup)
    backup_timer.start(30000)

    def offer_recovery():
        data = recovery_operations.load()
        if not data:
            return
        name = os.path.basename(data["file"]) if data.get("file") else "an unsaved note"
        when = data.get("saved_at", "").replace("T", " at ")
        reply = QMessageBox.question(
            window, "Recover Unsaved Notes",
            f"SharkPad closed before {name} was saved (last backup {when}).\n\nBring those notes back?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            editor.setPlainText(data["text"])
            current_file[0] = data.get("file") if data.get("file") and os.path.exists(os.path.dirname(data["file"])) else None
            editor.document().setModified(True)
            update_title()
            status_bar.showMessage("Notes recovered. Save them to keep them.", 6000)
        else:
            recovery_operations.clear()

    ai_operations.enable_spellcheck(editor)
    update_title()
    window.show()
    editor.setFocus()
    QTimer.singleShot(1000, splash.close)
    QTimer.singleShot(1200, offer_recovery)

    if setting_bool("dictation_used", False):
        QTimer.singleShot(4000, voice_operations.preload_model)


def boot():
    ai_operations.spell.unknown(["shark"])
    init_main()


QTimer.singleShot(100, boot)
sys.exit(app.exec())
