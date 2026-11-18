from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from sharkpad.help import pages
from sharkpad.help.help_dialog import HelpDialog

ISSUES_URL = "https://github.com/GabeyShark7/SharkPad/issues"


class HelpMenu:
    def __init__(self, win):
        self.win = win
        self.dialogs = {}
        menu = win.menuBar().addMenu("&Help")
        win.add_action(menu, "Getting Started", lambda: self.show("Getting Started", pages.GETTING_STARTED_HTML))
        win.add_action(menu, "Keyboard Shortcuts (F1)", self.show_shortcuts, ["F1"])
        win.add_action(menu, "Accessibility Features",
                       lambda: self.show("Accessibility Features", pages.ACCESSIBILITY_HTML))
        win.add_action(menu, "Voice Dictation Help", lambda: self.show("Voice Dictation Help", pages.DICTATION_HELP_HTML))
        menu.addSeparator()
        win.add_action(menu, "Report a Problem...", lambda: QDesktopServices.openUrl(QUrl(ISSUES_URL)))
        win.add_action(menu, "About SharkPad", lambda: self.show("About SharkPad", pages.ABOUT_HTML))

    def show_shortcuts(self):
        self.show("Keyboard Shortcuts", pages.shortcuts_html(pages.SHORTCUT_GROUPS))

    def show(self, title, body_html):
        dlg = self.dialogs.get(title)
        if dlg is None:
            dlg = HelpDialog(self.win, title, body_html)
            self.dialogs[title] = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
