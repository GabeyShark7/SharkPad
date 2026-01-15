import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit

#Application call
app = QApplication(sys.argv)
window = QMainWindow()
#Setting window title
window.setWindowTitle("Sharkpad")

#Text editior widget
editor = QPlainTextEdit()
editor.setPlaceholderText("Sharkpad — start writing…")

#Window sizing
window.setCentralWidget(editor)
window.resize(900, 600)
window.show()

sys.exit(app.exec())
