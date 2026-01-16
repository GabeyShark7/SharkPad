import sys
import os
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPlainTextEdit, QMenu, QWidget, QHBoxLayout,
    QFileDialog, QMessageBox
)
from PySide6.QtGui import QFont, QFontDatabase, QAction, QKeySequence, QShortcut
from PySide6.QtCore import Qt, QTimer

import file_operations
import view_operations
import preferences_operations
import ai_operations
import drawing_operations
from splash import SplashScreen

# -----------------------------
# Load Dyslexia Fonts
# -----------------------------
def load_dyslexia_fonts():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    regular_path = os.path.join(base_dir, "OpenDyslexic-Regular.ttf")
    bold_path = os.path.join(base_dir, "OpenDyslexic-Bold.ttf")

    regular_id = QFontDatabase.addApplicationFont(regular_path)
    bold_id = QFontDatabase.addApplicationFont(bold_path)

    regular_family = QFontDatabase.applicationFontFamilies(regular_id)[0] if regular_id != -1 else "Arial"
    bold_family = QFontDatabase.applicationFontFamilies(bold_id)[0] if bold_id != -1 else "Arial"

    return regular_family, bold_family

# -----------------------------
# Custom save_file for folder-first behavior
# -----------------------------
def save_file(editor, parent, current_file=None, drawing_pad=None):
    """Save text and drawing together in a user-named folder."""
    has_drawing = drawing_pad and drawing_pad.has_drawing()

    # Always ask for folder if no current file yet
    if not current_file:
        folder_path = QFileDialog.getExistingDirectory(parent, "Select or Create Folder to Save Project")
        if not folder_path:
            return None  # User canceled

        # Ask for project/file name
        project_name, _ = QFileDialog.getSaveFileName(
            parent,
            "Name Your File",
            folder_path,
            "Text Files (*.txt)"
        )
        if not project_name:
            return None  # User canceled

        # Ensure .txt extension
        if not project_name.endswith(".txt"):
            project_name += ".txt"

        current_file = project_name

    # Save text file
    with open(current_file, "w", encoding="utf-8") as f:
        f.write(editor.toPlainText())
    editor.document().setModified(False)

    # Save drawing if present
    if has_drawing:
        folder = os.path.dirname(current_file)
        base_name = os.path.splitext(os.path.basename(current_file))[0]
        drawing_path = os.path.join(folder, f"{base_name}_drawing.png")
        drawing_pad.save_drawing(drawing_path)

    QMessageBox.information(
        parent,
        "Saved",
        f"Saved:\n{os.path.basename(current_file)}" +
        (f"\n{os.path.basename(drawing_path)}" if has_drawing else "")
    )

    return current_file

# -----------------------------
# Main App 
# -----------------------------
app = QApplication(sys.argv)
dyslexia_regular_family, dyslexia_bold_family = load_dyslexia_fonts()

# Splash screen
splash = SplashScreen(width=600, height=300)
splash.show_splash()

# Preload LanguageTool
def preload_languagetool():
    ai_operations.tool.check("test")
    QApplication.processEvents()

# -----------------------------
# Init main window
# -----------------------------
def init_main():
    window = QMainWindow()
    window.setWindowTitle("SharkPad")
    window.resize(900, 600)

    # Central widget + layout
    central_widget = QWidget()
    main_layout = QHBoxLayout(central_widget)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(0)

    editor = QPlainTextEdit()
    editor.setPlaceholderText("Welcome to SharkPad. Start writing…")
    editor.setFont(QFont("Arial", 14))
    main_layout.addWidget(editor)

    drawing_pad = drawing_operations.create_drawing_pad()
    drawing_pad.setVisible(False)
    main_layout.addWidget(drawing_pad)

    window.setCentralWidget(central_widget)

    # -----------------------------
    # Menu bar
    # -----------------------------
    menu_bar = window.menuBar()

    # File menu
    file_menu = menu_bar.addMenu("File")
    new_action = QAction("New", window)
    open_action = QAction("Open", window)
    save_action = QAction("Save", window)
    save_as_action = QAction("Save As...", window)
    exit_action = QAction("Exit", window)
    exit_action.triggered.connect(app.quit)
    file_menu.addActions([new_action, open_action, save_action, save_as_action])
    file_menu.addSeparator()
    file_menu.addAction(exit_action)

    # View menu
    view_menu = menu_bar.addMenu("View")
    wrap_action = QAction("Word Wrap", window, checkable=True)
    wrap_action.setChecked(True)
    set_font_action = QAction("Set Font Size...", window)
    font_size_indicator = QAction(f"Font Size: {editor.font().pointSize()}", window)
    font_size_indicator.setDisabled(True)
    
    drawing_pad_action = QAction("Show Drawing Pad", window, checkable=True)
    drawing_pad_action.setChecked(False)
    
    view_menu.addAction(wrap_action)
    view_menu.addAction(set_font_action)
    view_menu.addAction(font_size_indicator)
    view_menu.addSeparator()
    view_menu.addAction(drawing_pad_action)

    # Dyslexia font menu
    dyslexia_menu = QMenu("Dyslexia Font", window)
    dyslexia_off_action = QAction("Off", window, checkable=True)
    dyslexia_off_action.setChecked(True)
    dyslexia_regular_action = QAction("Regular", window, checkable=True)
    dyslexia_bold_action = QAction("Bold", window, checkable=True)
    dyslexia_menu.addActions([dyslexia_off_action, dyslexia_regular_action, dyslexia_bold_action])
    view_menu.addMenu(dyslexia_menu)

    # Preferences menu
    preferences_menu = menu_bar.addMenu("Preferences")
    themes_menu = QMenu("Color Scheme", window)
    preferences_menu.addMenu(themes_menu)
    light_theme_action = QAction("Light", window)
    dark_theme_action = QAction("Dark", window)
    solarized_theme_action = QAction("Solarized", window)
    themes_menu.addActions([light_theme_action, dark_theme_action, solarized_theme_action])

    # -----------------------------
    # File actions
    # -----------------------------
    current_file = None

    def new_file_trigger():
        nonlocal current_file
        if editor.document().isModified() or (drawing_pad and drawing_pad.has_drawing()):
            reply = QMessageBox.question(
                window,
                "Unsaved Changes",
                "Do you want to save changes to the current file?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                current_file = save_file(editor, window, current_file, drawing_pad)
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        editor.clear()
        if drawing_pad:
            drawing_pad.canvas.clear_canvas()
        current_file = None
        window.setWindowTitle("SharkPad")

    def open_file_trigger():
        nonlocal current_file
        if editor.document().isModified() or (drawing_pad and drawing_pad.has_drawing()):
            reply = QMessageBox.question(
                window,
                "Unsaved Changes",
                "Do you want to save changes to the current file?",
                QMessageBox.StandardButton.Save | 
                QMessageBox.StandardButton.Discard | 
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Save:
                current_file = save_file(editor, window, current_file, drawing_pad)
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        file_path, _ = QFileDialog.getOpenFileName(window, "Open File", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                editor.setPlainText(f.read())
            if drawing_pad:
                drawing_pad.canvas.clear_canvas()
            current_file = file_path
            window.setWindowTitle(f"SharkPad — {current_file}")

    new_action.triggered.connect(new_file_trigger)
    open_action.triggered.connect(open_file_trigger)
    save_action.triggered.connect(lambda: save_file(editor, window, current_file, drawing_pad))

    # -----------------------------
    # View triggers
    # -----------------------------
    wrap_action.triggered.connect(lambda: wrap_action.setChecked(view_operations.toggle_word_wrap(editor)))
    set_font_action.triggered.connect(lambda: font_size_indicator.setText(f"Font Size: {view_operations.set_font_size(editor, window)}"))
    drawing_pad_action.triggered.connect(lambda: (
        drawing_pad.setVisible(not drawing_pad.isVisible()),
        drawing_pad_action.setChecked(drawing_pad.isVisible()),
        drawing_pad_action.setText("Hide Drawing Pad" if drawing_pad.isVisible() else "Show Drawing Pad")
    ))

    # Dyslexia triggers
    def apply_dyslexia_font():
        f = QFont(editor.font())
        f.setPointSize(editor.font().pointSize())
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

    def select_dyslexia_font(selected_action):
        for action in [dyslexia_off_action, dyslexia_regular_action, dyslexia_bold_action]:
            action.setChecked(False)
        selected_action.setChecked(True)
        apply_dyslexia_font()

    dyslexia_off_action.triggered.connect(lambda: select_dyslexia_font(dyslexia_off_action))
    dyslexia_regular_action.triggered.connect(lambda: select_dyslexia_font(dyslexia_regular_action))
    dyslexia_bold_action.triggered.connect(lambda: select_dyslexia_font(dyslexia_bold_action))

    # Theme triggers
    light_theme_action.triggered.connect(lambda: preferences_operations.apply_theme(editor, "Light"))
    dark_theme_action.triggered.connect(lambda: preferences_operations.apply_theme(editor, "Dark"))
    solarized_theme_action.triggered.connect(lambda: preferences_operations.apply_theme(editor, "Solarized"))

    # Enable AI spellcheck
    ai_operations.enable_spellcheck(editor)

    # -----------------------------
    # Drawing pad shortcuts
    # -----------------------------
    def setup_drawing_shortcuts():
        QShortcut(QKeySequence("Ctrl+Shift+D"), window, lambda: drawing_pad.set_mode('draw'))
        QShortcut(QKeySequence("Ctrl+Shift+S"), window, lambda: drawing_pad.set_mode('select'))
        QShortcut(QKeySequence("Ctrl+Shift+U"), window, drawing_pad.upload_image)
        QShortcut(QKeySequence("Ctrl+Shift+C"), window, drawing_pad.pick_color)
        QShortcut(QKeySequence("Ctrl+Shift+E"), window, drawing_pad.canvas.set_eraser)
        QShortcut(QKeySequence("Ctrl+Shift+]"), window, drawing_pad.bring_to_front)
        QShortcut(QKeySequence("Ctrl+Shift+["), window, drawing_pad.send_to_back)
        QShortcut(QKeySequence("Ctrl+]"), window, drawing_pad.bring_forward)
        QShortcut(QKeySequence("Ctrl+["), window, drawing_pad.send_backward)
        QShortcut(QKeySequence("Ctrl+Shift+Delete"), window, drawing_pad.delete_image)
        QShortcut(QKeySequence("Ctrl+Shift+Backspace"), window, drawing_pad.delete_image)
        # Ctrl+S Save
        QShortcut(QKeySequence("Ctrl+S"), window, lambda: save_file(editor, window, current_file, drawing_pad))

    setup_drawing_shortcuts()

    # Show main window
    window.show()
    QTimer.singleShot(1000, splash.close)

# -----------------------------
# Init sequence
# -----------------------------
def init_sequence():
    preload_languagetool()
    init_main()

QTimer.singleShot(100, init_sequence)
sys.exit(app.exec())
