from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPushButton, QTextBrowser, QVBoxLayout


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
