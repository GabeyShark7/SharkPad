import os

from PySide6.QtCore import QSettings, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QVBoxLayout, QWidget

from sharkpad import themes
from sharkpad.drawing.pad import DrawingPad
from sharkpad.editor.autosave_toggle import AutosaveToggle
from sharkpad.editor.editor_font import EditorFont
from sharkpad.editor.find_bar import FindBar
from sharkpad.editor.keyboard_helpers import LetterUndo
from sharkpad.editor.notes_editor import NotesEditor
from sharkpad.editor.read_aloud import ReadAloud
from sharkpad.editor.text_tools import text_stats
from sharkpad.files import project
from sharkpad.paths import resource_path
from sharkpad.shortcut_hints import apply_shortcut_hints
from sharkpad.spelling.underline import enable_spellcheck
from sharkpad.voice import speech_model
from sharkpad.window.accessibility_menu import AccessibilityMenu
from sharkpad.window.ai_menu import AiMenu
from sharkpad.window.edit_menu import EditMenu
from sharkpad.window.file_menu import FileMenu
from sharkpad.window.help_menu import HelpMenu
from sharkpad.window.preferences_menu import PreferencesMenu
from sharkpad.window.view_menu import ViewMenu


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1000, 650)
        self.setWindowIcon(QIcon(resource_path("shark_pad_icon.ico")))
        self.settings = QSettings("SharkPadApp", "Settings")
        self.current_file = None
        self.listening = False
        self.thinking = False

        self._build_layout()
        self.status_bar = self.statusBar()
        self.theme = self.settings.value("theme", "Light")
        if self.theme not in themes.THEMES:
            self.theme = "Light"
        themes.apply_theme(self.editor, self.theme)
        self.show_hints = self.setting_bool("show_shortcut_hints", True)
        self.editor_font = EditorFont(self.editor, self.settings)
        self.read_aloud = ReadAloud(self.editor)
        self._add_stats_label()

        self.file_menu = FileMenu(self)
        self.edit_menu = EditMenu(self)
        self.view_menu = ViewMenu(self)
        self.accessibility_menu = AccessibilityMenu(self)
        self.preferences_menu = PreferencesMenu(self)
        self.ai_menu = AiMenu(self)
        self.help_menu = HelpMenu(self)
        self._bind_drawing_shortcuts()
        self.bind(["Escape"], self.escape)
        apply_shortcut_hints(self, self.show_hints)

        self.editor.document().modificationChanged.connect(lambda _: self.update_title())
        self.canvas.changed.connect(self.update_title)
        enable_spellcheck(self.editor)
        self.update_title()

    def _build_layout(self):
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        editor_area = QWidget()
        editor_layout = QVBoxLayout(editor_area)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        header = QWidget()
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(8, 5, 8, 5)
        title = QLabel("Notes")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_row.addWidget(title)
        header_row.addStretch()
        self.notes_autosave = AutosaveToggle("notes")
        header_row.addWidget(self.notes_autosave)
        editor_layout.addWidget(header)

        self.editor = NotesEditor()
        self.editor.setPlaceholderText("Welcome to SharkPad. Start writing… (Press F1 for help)")
        self.editor.setAccessibleName("Notes")
        self.editor.setAccessibleDescription("Type your notes here")
        editor_layout.addWidget(self.editor)
        LetterUndo(self.editor)

        self.find_bar = FindBar(self.editor)
        editor_layout.addWidget(self.find_bar)
        main_layout.addWidget(editor_area, 1)

        self.drawing_pad = DrawingPad()
        self.drawing_pad.setAccessibleName("Drawing pad")
        self.drawing_pad.setVisible(self.setting_bool("drawing_pad_visible", True))
        self.canvas = self.drawing_pad.canvas
        main_layout.addWidget(self.drawing_pad)
        self.setCentralWidget(central)

    def _add_stats_label(self):
        stats_label = QLabel()
        stats_label.setAccessibleName("Document statistics")
        self.status_bar.addPermanentWidget(stats_label)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(150)
        timer.timeout.connect(lambda: stats_label.setText(text_stats(self.editor)))
        self.editor.textChanged.connect(timer.start)
        self.editor.cursorPositionChanged.connect(timer.start)
        self.editor.selectionChanged.connect(timer.start)
        timer.start()

    def _bind_drawing_shortcuts(self):
        canvas = self.canvas
        self.bind(["Ctrl+Shift+D"], lambda: canvas.set_tool("draw"))
        self.bind(["Ctrl+Shift+E"], lambda: canvas.set_tool("erase"))
        self.bind(["Ctrl+Shift+H"], lambda: canvas.set_tool("highlight"))
        self.bind(["Ctrl+Shift+X"], lambda: canvas.set_tool("text"))
        self.bind(["Ctrl+Shift+A"], lambda: canvas.set_tool("select"))
        self.bind(["Ctrl+Shift+U"], self.drawing_pad.upload_image)
        self.bind(["Ctrl+Shift+C"], self.drawing_pad.colors.pick_color)
        self.bind(["Ctrl+Shift+]", "Ctrl+}", "Ctrl+Shift+}"], canvas.bring_to_front)
        self.bind(["Ctrl+Shift+[", "Ctrl+{", "Ctrl+Shift+{"], canvas.send_to_back)
        self.bind(["Ctrl+]"], canvas.bring_forward)
        self.bind(["Ctrl+["], canvas.send_backward)
        self.bind(["Ctrl+Shift+Del"], canvas.delete_selection)

    def setting_bool(self, key, default):
        return str(self.settings.value(key, default)).lower() == "true"

    def bind(self, keys, callback):
        for k in keys:
            QShortcut(QKeySequence(k), self, callback)

    def add_action(self, menu, text, callback, keys=(), checkable=False, checked=False):
        action = QAction(text, self, checkable=checkable)
        if checkable:
            action.setChecked(checked)
            action.toggled.connect(callback)
        else:
            action.triggered.connect(callback)
        menu.addAction(action)
        self.bind(keys, callback)
        return action

    def add_choice_menu(self, parent_menu, title, choices, current, on_pick):
        submenu = parent_menu.addMenu(title)
        group = QActionGroup(submenu)
        for label, value in choices:
            a = submenu.addAction(label)
            a.setCheckable(True)
            a.setChecked(value == current)
            group.addAction(a)
            a.triggered.connect(lambda _=False, v=value: on_pick(v))
        return submenu

    def is_dirty(self):
        return self.editor.document().isModified() or self.canvas.modified

    def display_name(self):
        if not self.current_file:
            return "Untitled"
        if project.is_project_notes(self.current_file):
            return project.split_project(self.current_file)[1]
        return os.path.basename(self.current_file)

    def update_title(self):
        extra = ""
        if self.thinking:
            extra = " - AI Teacher is thinking..."
        elif self.listening:
            extra = " - listening"
        self.setWindowTitle(f"{self.display_name()}[*] - SharkPad{extra}")
        self.setWindowModified(self.is_dirty())

    def escape(self):
        if self.read_aloud.is_speaking():
            self.read_aloud.stop()
        elif self.find_bar.isVisible():
            self.find_bar.close_bar()
        elif self.view_menu.focus_mode:
            self.view_menu.toggle_focus_mode()

    def start(self):
        self.show()
        self.editor.setFocus()
        QTimer.singleShot(1200, self.file_menu.backup.offer_recovery)
        if self.setting_bool("dictation_used", False):
            QTimer.singleShot(4000, speech_model.preload_model)

    def closeEvent(self, event):
        if not self.file_menu.before_close():
            event.ignore()
            return
        super().closeEvent(event)
