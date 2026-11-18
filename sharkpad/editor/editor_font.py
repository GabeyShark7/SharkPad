from PySide6.QtGui import QFont, QFontDatabase

from sharkpad.paths import resource_path

DEFAULT_FONT_SIZE = 14
MIN_SIZE, MAX_SIZE = 6, 96
TEXT_SPACING = {"Normal": (0.0, 0.0), "Wide": (1.5, 4.0), "Extra Wide": (3.0, 8.0)}
DYSLEXIA_MODES = ["Off", "Regular", "Bold"]


def _load_font(filename):
    font_id = QFontDatabase.addApplicationFont(resource_path(filename))
    return QFontDatabase.applicationFontFamilies(font_id)[0] if font_id != -1 else "Arial"


class EditorFont:
    def __init__(self, editor, settings):
        self.editor = editor
        self.settings = settings
        self.families = {"Regular": _load_font("OpenDyslexic-Regular.ttf"),
                         "Bold": _load_font("OpenDyslexic-Bold.ttf")}
        try:
            size = int(settings.value("font_size", DEFAULT_FONT_SIZE))
        except (TypeError, ValueError):
            size = DEFAULT_FONT_SIZE
        self.size = max(MIN_SIZE, min(MAX_SIZE, size))
        self.dyslexia = settings.value("dyslexia_font", "Off")
        self.spacing = settings.value("text_spacing", "Normal")
        self.apply()

    def apply(self):
        f = QFont(self.families.get(self.dyslexia, "Arial"), self.size)
        f.setBold(self.dyslexia == "Bold")
        letter, word = TEXT_SPACING.get(self.spacing, (0.0, 0.0))
        f.setLetterSpacing(QFont.AbsoluteSpacing, letter)
        f.setWordSpacing(word)
        self.editor.setFont(f)
        self.settings.setValue("font_size", self.size)
        self.settings.setValue("dyslexia_font", self.dyslexia)
        self.settings.setValue("text_spacing", self.spacing)

    def set_size(self, size):
        self.size = max(MIN_SIZE, min(MAX_SIZE, size))
        self.apply()

    def set_dyslexia(self, mode):
        self.dyslexia = mode
        self.apply()

    def set_spacing(self, name):
        self.spacing = name
        self.apply()
