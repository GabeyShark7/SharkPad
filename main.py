import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from sharkpad.splash import SplashScreen
from sharkpad.voice import dictation
from sharkpad.window.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SharkPad")
    app.setOrganizationName("SharkPadApp")
    app.aboutToQuit.connect(dictation.wait_for_shutdown)
    splash = SplashScreen()
    splash.show_splash()
    windows = []

    def start():
        window = MainWindow()
        windows.append(window)
        window.start()
        QTimer.singleShot(1000, splash.close)

    QTimer.singleShot(100, start)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
