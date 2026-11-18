from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget


class AutosaveToggle(QWidget):
    toggled = Signal(bool)

    def __init__(self, what, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.status = QLabel()
        self.status.setStyleSheet("color: gray; font-size: 11px;")
        self.box = QCheckBox("Autosave")
        self.box.setToolTip(f"Save the {what} automatically after every change")
        self.box.setAccessibleName(f"Autosave {what}")
        row.addWidget(self.status)
        row.addWidget(self.box)
        self.box.toggled.connect(self.toggled.emit)

    def isChecked(self):
        return self.box.isChecked()

    def setChecked(self, on):
        self.box.blockSignals(True)
        self.box.setChecked(on)
        self.box.blockSignals(False)

    def set_status(self, text):
        self.status.setText(text)
