from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout


class AskDialog(QDialog):
    def __init__(self, parent, passage):
        super().__init__(parent)
        self.setWindowTitle("Ask the AI Teacher")
        self.setFixedWidth(460)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>About this part of your notes:</b>"))
        preview = QPlainTextEdit(passage)
        preview.setReadOnly(True)
        preview.setFixedHeight(90)
        preview.setAccessibleName("Highlighted notes")
        layout.addWidget(preview)

        layout.addWidget(QLabel("<b>Your question:</b>"))
        self.question_input = QLineEdit()
        self.question_input.setPlaceholderText("What do you want to know?")
        self.question_input.setAccessibleName("Your question")
        layout.addWidget(self.question_input)
        hint = QLabel("The answer appears below the highlighted part. You can keep working while it thinks.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self.ask_btn = QPushButton("Ask")
        self.ask_btn.setDefault(True)
        self.ask_btn.setEnabled(False)
        self.ask_btn.clicked.connect(self.accept)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(self.ask_btn)
        layout.addLayout(buttons)

        self.question_input.textChanged.connect(lambda t: self.ask_btn.setEnabled(bool(t.strip())))
        self.question_input.setFocus(Qt.OtherFocusReason)

    def question(self):
        return self.question_input.text().strip()
