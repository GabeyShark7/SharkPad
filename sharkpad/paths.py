import os
import sys

from PySide6.QtCore import QStandardPaths

APP_FOLDER = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    return os.path.join(APP_FOLDER, relative_path)


def app_data_path(filename):
    folder = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    if not folder:
        folder = os.path.join(os.path.expanduser("~"), ".sharkpad")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, filename)
