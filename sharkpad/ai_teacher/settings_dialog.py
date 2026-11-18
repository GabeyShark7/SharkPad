from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from sharkpad.ai_teacher import teacher

PRESET_EXAMPLE = (
    "Example:\n"
    "- Explain like I'm in 9th grade\n"
    "- Always end with one practice question\n"
    "- Use chemistry examples when you can\n"
    "- Never just give me homework answers"
)


def _label(text, style):
    label = QLabel(text)
    label.setStyleSheet(style)
    label.setWordWrap(True)
    return label


class TeacherSettingsDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle("AI Teacher Settings")
        self.setFixedWidth(450)
        self.settings = settings
        layout = QVBoxLayout(self)

        layout.addWidget(_label("Setup AI Teacher", "font-size: 14px; font-weight: bold;"))
        layout.addWidget(_label("Step 1: Get your free API key", "font-size: 12px; font-weight: bold; margin-top: 10px;"))
        link_label = _label('<a href="https://console.groq.com/keys">Click here to get a free Groq API key</a>',
                            "font-size: 11px; margin-left: 10px;")
        link_label.setOpenExternalLinks(True)
        layout.addWidget(link_label)
        layout.addWidget(_label("(Sign up or log in, then create a new API key)",
                                "font-size: 10px; color: gray; margin-left: 10px;"))
        layout.addWidget(_label("Step 2: Enter your API key below", "font-size: 12px; font-weight: bold; margin-top: 15px;"))

        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setPlaceholderText("gsk_...")
        self.token_input.setText(self.settings.value("api_key", ""))
        layout.addWidget(self.token_input)
        layout.addWidget(_label("Your key is saved locally and remembered for next time.", "font-size: 10px; color: gray;"))

        layout.addWidget(_label("Teacher Preset (optional)", "font-size: 12px; font-weight: bold; margin-top: 15px;"))
        layout.addWidget(_label("Tell the AI Teacher how to act, what it should do, and what it must never do. "
                                "It follows this every time.", "font-size: 10px; color: gray;"))
        self.preset_input = QPlainTextEdit()
        self.preset_input.setPlaceholderText(PRESET_EXAMPLE)
        self.preset_input.setAccessibleName("Teacher preset")
        self.preset_input.setPlainText(self.settings.value("teacher_preset", ""))
        self.preset_input.setFixedHeight(120)
        layout.addWidget(self.preset_input)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; padding: 5px 15px;")
        save_btn.clicked.connect(self.save)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        layout.addSpacing(15)
        layout.addLayout(btn_layout)

    def save(self):
        token = self.token_input.text().strip()
        if token and not token.startswith("gsk_"):
            QMessageBox.warning(self, "Invalid Key", "Groq API keys must start with 'gsk_'.\n\nPlease check your key and try again.")
            return
        if token:
            self.settings.setValue("api_key", token)
            teacher.set_api_token(token)
        preset = self.preset_input.toPlainText().strip()
        self.settings.setValue("teacher_preset", preset)
        teacher.set_preset(preset)
        QMessageBox.information(self, "Saved", "AI Teacher settings saved!")
        self.accept()
