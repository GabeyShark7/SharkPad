from sharkpad import themes
from sharkpad.files import project
from sharkpad.shortcut_hints import apply_shortcut_hints

NOTE_TYPE_LABELS = {".txt": ".txt  (plain text)", ".md": ".md  (Markdown)", ".html": ".html  (web page)"}
IMAGE_TYPE_LABELS = {".png": ".png  (best quality, stays editable)", ".jpg": ".jpg  (smaller file, stays editable)",
                     ".bmp": ".bmp  (reopens as a flat picture)", ".webp": ".webp  (reopens as a flat picture)",
                     ".tiff": ".tiff  (reopens as a flat picture)"}


class PreferencesMenu:
    def __init__(self, win):
        self.win = win
        settings = win.settings
        menu = win.menuBar().addMenu("&Preferences")

        themes_menu = win.add_choice_menu(menu, "Color Scheme", [(t, t) for t in themes.THEMES], win.theme,
                                          self.set_theme)
        self.theme_actions = themes_menu.actions()

        types_menu = menu.addMenu("Save File Types")
        for title, key, choices, labels, current in (
                ("Notes", "notes_ext", project.NOTE_EXTENSIONS, NOTE_TYPE_LABELS,
                 project.chosen_notes_ext(settings)),
                ("Drawing", "image_ext", project.image_extensions(), IMAGE_TYPE_LABELS,
                 project.chosen_image_ext(settings))):
            win.add_choice_menu(types_menu, title, [(labels.get(e, e), e) for e in choices], current,
                                lambda ext, k=key, t=title: self._set_file_type(k, ext, t))

        win.add_action(menu, "Show Shortcut Hints", self.toggle_shortcut_hints, checkable=True, checked=win.show_hints)

    def set_theme(self, theme):
        win = self.win
        themes.apply_theme(win.editor, theme)
        win.settings.setValue("theme", theme)
        win.theme = theme
        for a in self.theme_actions:
            a.setChecked(a.text() == theme)
        win.accessibility_menu.theme_changed(theme)

    def _set_file_type(self, key, ext, title):
        self.win.settings.setValue(key, ext)
        self.win.status_bar.showMessage(f"{title} will be saved as {ext} from now on.", 4000)

    def toggle_shortcut_hints(self, checked):
        self.win.show_hints = checked
        self.win.settings.setValue("show_shortcut_hints", checked)
        apply_shortcut_hints(self.win, checked)
