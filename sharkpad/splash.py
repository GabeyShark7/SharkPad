from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen


class SplashScreen(QSplashScreen):
    def __init__(self, width=600, height=300):
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#1E1E1E"))

        painter = QPainter(pixmap)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Arial", 32, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "SharkPad is loading...")
        painter.end()

        super().__init__(pixmap)

        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width() - width) // 2, (screen.height() - height) // 2)

    def show_splash(self):
        """
        Show the splash screen and force it to render immediately.
        """
        self.show()
        QApplication.processEvents()
