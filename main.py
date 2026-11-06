import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPlainTextEdit, QMenu, QWidget, QHBoxLayout, QVBoxLayout,
    QFileDialog, QMessageBox, QProgressBar, QLabel, QSlider, QDialog, QPushButton, QLineEdit
)
from PySide6.QtGui import QFont, QFontDatabase, QAction, QKeySequence, QShortcut, QIcon
from PySide6.QtCore import Qt, QTimer, QSettings

import file_operations
import view_operations
import preferences_operations
import ai_operations
import voice_operations
import drawing_operations
import summarization_operations
from splash import SplashScreen


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller unpacks bundled files to a temp folder stored in sys._MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


# AI Teacher (Groq) API Key Dialog
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

        # Pre-fill with the key saved from a previous session
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

# Mic Sensitivity Dialog
class MicSensitivityDialog(QDialog):
    def __init__(self, parent=None, current_value=300):
        super().__init__(parent)
        self.setWindowTitle("Microphone Sensitivity")
        self.setModal(False)
        self.resize(400, 200)
        
        layout = QVBoxLayout(self)
        info_label = QLabel("Adjust microphone sensitivity:\nLower = picks up quieter sounds\nHigher = requires louder speech")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        self.level_label = QLabel("Audio Level:")
        layout.addWidget(self.level_label)
        
        self.level_bar = QProgressBar()
        self.level_bar.setRange(0, 100)
        self.level_bar.setValue(0)
        layout.addWidget(self.level_bar)
        
        slider_label = QLabel(f"Sensitivity Threshold: {current_value}")
        layout.addWidget(slider_label)
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(100, 4000)
        self.slider.setValue(current_value)
        
        def update_label(value):
            slider_label.setText(f"Sensitivity Threshold: {value}")
            voice_operations.set_sensitivity(value)
        
        self.slider.valueChanged.connect(update_label)
        layout.addWidget(self.slider)
        
        preset_layout = QHBoxLayout()
        for label, val in [("Quiet", 200), ("Normal", 300), ("Noisy", 500)]:
            btn = QPushButton(f"{label} ({val})")
            btn.clicked.connect(lambda v=val: self.slider.setValue(v))
            preset_layout.addWidget(btn)
        
        layout.addLayout(preset_layout)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
    
    def update_level(self, level):
        self.level_bar.setValue(level)

# Load Dyslexia Fonts
def load_dyslexia_fonts():
    regular_path = resource_path("OpenDyslexic-Regular.ttf")
    bold_path = resource_path("OpenDyslexic-Bold.ttf")
    regular_id = QFontDatabase.addApplicationFont(regular_path)
    bold_id = QFontDatabase.addApplicationFont(bold_path)
    regular_family = QFontDatabase.applicationFontFamilies(regular_id)[0] if regular_id != -1 else "Arial"
    bold_family = QFontDatabase.applicationFontFamilies(bold_id)[0] if bold_id != -1 else "Arial"
    return regular_family, bold_family

# File Operations
def open_file(editor, parent, drawing_pad=None):
    file_path, _ = QFileDialog.getOpenFileName(parent, "Open File", "", "Text Files (*.txt);;All Files (*)")
    if not file_path: return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            editor.setPlainText(f.read())
        editor.document().setModified(False)
        if drawing_pad:
            folder = os.path.dirname(file_path)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            drawing_path = os.path.join(folder, f"{base_name}_drawing.png")
            if os.path.exists(drawing_path): drawing_pad.load_drawing(drawing_path)
        return file_path
    except Exception as e:
        QMessageBox.critical(parent, "Error", f"Could not open file:\n{str(e)}")
        return None

def save_file(editor, parent, current_file=None, drawing_pad=None):
    has_drawing = drawing_pad and drawing_pad.has_drawing()
    if not current_file:
        folder_path = QFileDialog.getExistingDirectory(parent, "Select or Create Folder to Save Project")
        if not folder_path: return None
        project_name, _ = QFileDialog.getSaveFileName(parent, "Name Your File", folder_path, "Text Files (*.txt)")
        if not project_name: return None
        if not project_name.endswith(".txt"): project_name += ".txt"
        current_file = project_name
    with open(current_file, "w", encoding="utf-8") as f:
        f.write(editor.toPlainText())
    editor.document().setModified(False)
    if has_drawing:
        folder = os.path.dirname(current_file)
        base_name = os.path.splitext(os.path.basename(current_file))[0]
        drawing_path = os.path.join(folder, f"{base_name}_drawing.png")
        drawing_pad.save_drawing(drawing_path)
    QMessageBox.information(parent, "Saved", f"Saved: {os.path.basename(current_file)}")
    return current_file

def save_file_as(editor, parent, drawing_pad=None):
    file_path, _ = QFileDialog.getSaveFileName(parent, "Save As", "", "Text Files (*.txt);;All Files (*)")
    if not file_path: return None
    if not file_path.endswith(".txt"): file_path += ".txt"
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(editor.toPlainText())
        editor.document().setModified(False)
        if drawing_pad:
            folder = os.path.dirname(file_path)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            drawing_path = os.path.join(folder, f"{base_name}_drawing.png")
            drawing_pad.save_drawing(drawing_path)
        return file_path
    except Exception as e:
        QMessageBox.critical(parent, "Error", f"Could not save file:\n{str(e)}")
        return None

# Main App Initialization
app = QApplication(sys.argv)
dyslexia_regular_family, dyslexia_bold_family = load_dyslexia_fonts()
splash = SplashScreen(width=600, height=300)
splash.show_splash()

def init_main():
    window = QMainWindow()
    window.setWindowTitle("SharkPad")
    window.resize(900, 600)
    window.setWindowIcon(QIcon(resource_path("shark_pad_icon.ico")))

    # Persisted user settings (API key, font size, theme, shortcut hints)
    settings = QSettings("SharkPadApp", "Settings")

    central_widget = QWidget()
    main_layout = QHBoxLayout(central_widget)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    editor = QPlainTextEdit()
    editor.setPlaceholderText("Welcome to SharkPad. Start writing…")
    saved_font_size = int(settings.value("font_size", 14))
    editor.setFont(QFont("Arial", saved_font_size))
    main_layout.addWidget(editor)

    drawing_pad = drawing_operations.create_drawing_pad()
    drawing_pad.setVisible(True)
    main_layout.addWidget(drawing_pad)

    window.setCentralWidget(central_widget)
    menu_bar = window.menuBar()

    current_file = [None]
    mic_dialog = [None]
    current_sensitivity = [300]

    # Restore saved API key and theme
    saved_token = settings.value("api_key")
    if saved_token:
        summarization_operations.set_api_token(saved_token)

    saved_theme = settings.value("theme", "Light")
    preferences_operations.apply_theme(editor, saved_theme)

    # File Menu
    file_menu = menu_bar.addMenu("File")
    
    def new_file_trigger():
        if editor.document().isModified():
            if QMessageBox.question(window, "Unsaved Changes", "Continue?") == QMessageBox.No: return
        editor.clear()
        if drawing_pad: drawing_pad.canvas.clear_canvas()
        current_file[0] = None
        window.setWindowTitle("SharkPad")

    def open_file_trigger():
        result = open_file(editor, window, drawing_pad)
        if result:
            current_file[0] = result
            window.setWindowTitle(f"SharkPad - {os.path.basename(result)}")

    new_action = QAction("New", window)
    new_action.triggered.connect(new_file_trigger)
    open_action = QAction("Open (Ctrl+O)", window)
    open_action.triggered.connect(open_file_trigger)
    save_action = QAction("Save (Ctrl+S)", window)
    save_action.triggered.connect(lambda: save_file(editor, window, current_file[0], drawing_pad))
    save_as_action = QAction("Save As (Ctrl+Shift+S)", window)
    save_as_action.triggered.connect(lambda: save_file_as(editor, window, drawing_pad))
    
    file_menu.addActions([new_action, open_action, save_action, save_as_action])

    # View Menu
    view_menu = menu_bar.addMenu("View")
    wrap_action = QAction("Word Wrap", window, checkable=True)
    wrap_action.setChecked(True)
    wrap_action.triggered.connect(lambda: view_operations.toggle_word_wrap(editor))
    
    set_font_size_action = QAction("Set Font Size...", window)
    font_size_indicator = QAction(f"Font Size: {editor.font().pointSize()}", window)
    font_size_indicator.setDisabled(True)
    def change_font_trigger():
        new_size = view_operations.set_font_size(editor, window)
        font_size_indicator.setText(f"Font Size: {new_size}")
        settings.setValue("font_size", new_size)

    set_font_size_action.triggered.connect(change_font_trigger)

    drawing_pad_action = QAction("Show Drawing Pad", window, checkable=True)
    drawing_pad_action.setChecked(True)
    drawing_pad_action.triggered.connect(lambda: drawing_pad.setVisible(drawing_pad_action.isChecked()))
    
    view_menu.addActions([wrap_action, set_font_size_action, font_size_indicator])
    view_menu.addSeparator()
    view_menu.addAction(drawing_pad_action)

    # Dyslexia Font Menu
    dyslexia_menu = QMenu("Dyslexia Font", window)
    dyslexia_off_action = QAction("Off", window, checkable=True)
    dyslexia_off_action.setChecked(True)
    dyslexia_regular_action = QAction("Regular", window, checkable=True)
    dyslexia_bold_action = QAction("Bold", window, checkable=True)

    def select_dyslexia_font(selected_action):
        for action in [dyslexia_off_action, dyslexia_regular_action, dyslexia_bold_action]:
            action.setChecked(False)
        selected_action.setChecked(True)
        f = QFont(editor.font())
        if dyslexia_regular_action.isChecked():
            f.setFamily(dyslexia_regular_family)
            f.setBold(False)
        elif dyslexia_bold_action.isChecked():
            f.setFamily(dyslexia_bold_family)
            f.setBold(True)
        else:
            f.setFamily("Arial")
            f.setBold(False)
        editor.setFont(f)

    dyslexia_off_action.triggered.connect(lambda: select_dyslexia_font(dyslexia_off_action))
    dyslexia_regular_action.triggered.connect(lambda: select_dyslexia_font(dyslexia_regular_action))
    dyslexia_bold_action.triggered.connect(lambda: select_dyslexia_font(dyslexia_bold_action))
    
    dyslexia_menu.addActions([dyslexia_off_action, dyslexia_regular_action, dyslexia_bold_action])
    view_menu.addMenu(dyslexia_menu)

    # Preferences Menu
    preferences_menu = menu_bar.addMenu("Preferences")
    themes_menu = QMenu("Color Scheme", window)

    def apply_and_save_theme(t):
        preferences_operations.apply_theme(editor, t)
        settings.setValue("theme", t)

    for theme in ["Light", "Dark", "Solarized"]:
        action = QAction(theme, window)
        action.triggered.connect(lambda _, t=theme: apply_and_save_theme(t))
        themes_menu.addAction(action)
    preferences_menu.addMenu(themes_menu)

    # Show or hide the "(Ctrl+...)" hints on buttons and menu items
    show_hints = [str(settings.value("show_shortcut_hints", "true")).lower() == "true"]
    shortcut_hints_action = QAction("Show Shortcut Hints", window, checkable=True)
    shortcut_hints_action.setChecked(show_hints[0])

    def toggle_shortcut_hints(checked):
        show_hints[0] = checked
        settings.setValue("show_shortcut_hints", checked)
        preferences_operations.apply_shortcut_hints(window, checked)

    shortcut_hints_action.toggled.connect(toggle_shortcut_hints)
    preferences_menu.addAction(shortcut_hints_action)

    # AI Tools Menu
    ai_menu = menu_bar.addMenu("AI Tools")
    
    # AI Teacher Settings (Token)
    ai_settings_action = QAction("AI Teacher Settings (Token)...", window)
    ai_settings_action.triggered.connect(lambda: OpenAISettingsDialog(window).exec())
    ai_menu.addAction(ai_settings_action)
    ai_menu.addSeparator()

    # Voice Dictation
    voice_action = QAction("Toggle Voice Dictation (Ctrl+Shift+V)", window)
    def toggle_voice_ui():
        def level_update(l): 
            if mic_dialog[0] and mic_dialog[0].isVisible(): mic_dialog[0].update_level(l)
        is_on = voice_operations.toggle_voice(editor, level_update, current_sensitivity[0])
        window.setWindowTitle("SharkPad is listening..." if is_on else "SharkPad")
        preferences_operations.set_hinted_text(
            voice_action,
            "Stop Dictation (Ctrl+Shift+V)" if is_on else "Voice Dictation (Ctrl+Shift+V)",
            show_hints[0],
        )
        if is_on and mic_dialog[0]: mic_dialog[0].show()
        elif not is_on and mic_dialog[0]: mic_dialog[0].close()
    
    voice_action.triggered.connect(toggle_voice_ui)
    ai_menu.addAction(voice_action)

    # Mic Sensitivity
    mic_settings_action = QAction("Microphone Sensitivity...", window)
    def show_mic_settings():
        if not mic_dialog[0]:
            mic_dialog[0] = MicSensitivityDialog(window, current_sensitivity[0])
            mic_dialog[0].slider.valueChanged.connect(lambda v: current_sensitivity.__setitem__(0, v))
        mic_dialog[0].show()
    mic_settings_action.triggered.connect(show_mic_settings)
    ai_menu.addAction(mic_settings_action)
    ai_menu.addSeparator()

    # AI Teacher Explain
    summarize_action = QAction("AI Teacher Explain (Ctrl+Shift+T)", window)
    def summarize_text_trigger():
        text = editor.toPlainText()
        if not text.strip():
            QMessageBox.information(window, "No Text", "Please provide some content for me to explain!")
            return
        window.setWindowTitle("SharkPad — Teacher is thinking...")
        QApplication.processEvents()
        
        summary = summarization_operations.summarize_text(text, max_sentences=5)
        
        editor.setPlainText(summary)
        window.setWindowTitle("SharkPad" if not current_file[0] else f"SharkPad - {os.path.basename(current_file[0])}")
        QMessageBox.information(window, "AI Teacher", "Explanation complete!")

    summarize_action.triggered.connect(summarize_text_trigger)
    ai_menu.addAction(summarize_action)

    # Shortcuts
    QShortcut(QKeySequence("Ctrl+O"), window, open_file_trigger)
    QShortcut(QKeySequence("Ctrl+S"), window, lambda: save_file(editor, window, current_file[0], drawing_pad))
    QShortcut(QKeySequence("Ctrl+Shift+S"), window, lambda: save_file_as(editor, window, drawing_pad))
    QShortcut(QKeySequence("Ctrl+Shift+V"), window, toggle_voice_ui)
    QShortcut(QKeySequence("Ctrl+Shift+T"), window, summarize_text_trigger)
    QShortcut(QKeySequence("Ctrl+Shift+D"), window, lambda: drawing_pad.set_mode('draw'))
    QShortcut(QKeySequence("Ctrl+Shift+E"), window, drawing_pad.canvas.set_eraser)

    # Drawing pad shortcuts (these match the hints shown on the buttons)
    def add_shortcuts(keys, callback):
        for k in keys:
            QShortcut(QKeySequence(k), window, callback)

    add_shortcuts(["Ctrl+Shift+A"], lambda: drawing_pad.set_mode('select'))
    add_shortcuts(["Ctrl+Shift+U"], drawing_pad.upload_image)
    add_shortcuts(["Ctrl+Shift+C"], drawing_pad.pick_color)
    # Shift turns [ and ] into { and } on most keyboards, so bind both forms
    add_shortcuts(["Ctrl+Shift+]", "Ctrl+}", "Ctrl+Shift+}"], drawing_pad.bring_to_front)
    add_shortcuts(["Ctrl+Shift+[", "Ctrl+{", "Ctrl+Shift+{"], drawing_pad.send_to_back)
    add_shortcuts(["Ctrl+]"], drawing_pad.bring_forward)
    add_shortcuts(["Ctrl+["], drawing_pad.send_backward)
    add_shortcuts(["Ctrl+Shift+Del"], drawing_pad.delete_image)

    preferences_operations.apply_shortcut_hints(window, show_hints[0])

    ai_operations.enable_spellcheck(editor)
    window.show()
    QTimer.singleShot(1000, splash.close)

def boot():
    ai_operations.spell.unknown(["shark"])
    init_main()

QTimer.singleShot(100, boot)
sys.exit(app.exec())