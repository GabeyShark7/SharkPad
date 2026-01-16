# splash.py
from PySide6.QtWidgets import QSplashScreen, QApplication
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor
from PySide6.QtCore import Qt

class SplashScreen(QSplashScreen):
    def __init__(self, width=900, height=600, message="SharkPad is loading...", bg_color="#1E1E1E", text_color="white"):
        # Create a pixmap with the background color
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor(bg_color))
        
        # Draw the text on the pixmap
        painter = QPainter(pixmap)
        painter.setPen(QColor(text_color))
        painter.setFont(QFont("Arial", 32, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, message)
        painter.end()
        
        # Initialize QSplashScreen with the pixmap
        super().__init__(pixmap)
        
        # Center on screen
        screen_geometry = QApplication.primaryScreen().geometry()
        x = (screen_geometry.width() - width) // 2
        y = (screen_geometry.height() - height) // 2
        self.move(x, y)
    
    def show_splash(self):
        """
        Show the splash screen and force it to render immediately.
        """
        self.show()
        QApplication.processEvents()  # ensure it draws immediately