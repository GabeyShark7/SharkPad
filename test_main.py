import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit, QMenu
from PySide6.QtGui import QAction, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QColor, QFontDatabase
from PySide6.QtCore import Qt, QRegularExpression, QTimer

app = QApplication(sys.argv)
window = QMainWindow()

font_id = QFontDatabase.addApplicationFont("OpenDyslexic-Regular.ttf")
font_family = QFontDatabase.applicationFontFamilies(font_id)[0]

editor = QPlainTextEdit()
editor.setFont(QFont(font_family, 14))
window.setCentralWidget(editor)

menu_bar = window.menuBar()
file_menu = menu_bar.addMenu("File")
exit_action = QAction("Exit", window)
exit_action.triggered.connect(app.quit)
file_menu.addAction(exit_action)

window.resize(900, 600)
window.show()
sys.exit(app.exec())
