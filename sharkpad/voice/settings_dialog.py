from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout

from sharkpad.voice import dictation, mic, speech_model
from sharkpad.voice.level_meter import LevelMeter


def _gray_label(text=""):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("color: gray;")
    return label


class VoiceSettingsDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Voice Dictation Settings")
        self.setModal(False)
        self.setFixedWidth(500)
        self.monitor = mic.MicMonitor()

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("<b>Microphone</b>"))
        self.device_box = QComboBox()
        self.device_box.addItem("System default", "")
        for name in mic.list_input_devices():
            self.device_box.addItem(name, name)
        self.device_box.setCurrentIndex(max(0, self.device_box.findData(mic.get_device())))
        self.device_box.currentIndexChanged.connect(self._device_changed)
        layout.addWidget(self.device_box)

        layout.addWidget(QLabel("<b>Where are you?</b> Pick one to set the slider for you."))
        preset_row = QHBoxLayout()
        self.preset_buttons = {}
        for label, value, tip in mic.PRESETS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setAutoDefault(False)
            btn.setToolTip(tip)
            btn.setStyleSheet(
                "QPushButton:checked { background-color: palette(highlight);"
                " color: palette(highlighted-text); font-weight: bold; }"
            )
            btn.clicked.connect(lambda _=False, v=value: self.slider.setValue(v))
            self.preset_buttons[value] = btn
            preset_row.addWidget(btn)
        layout.addLayout(preset_row)
        self.preset_hint = _gray_label()
        layout.addWidget(self.preset_hint)

        layout.addWidget(QLabel("<b>Sensitivity</b>"))
        slider_row = QHBoxLayout()
        slider_row.addWidget(QLabel("Low"))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(mic.get_sensitivity())
        self.slider.valueChanged.connect(self._sensitivity_changed)
        slider_row.addWidget(self.slider, 1)
        slider_row.addWidget(QLabel("High"))
        self.slider_value = QLabel()
        self.slider_value.setMinimumWidth(30)
        self.slider_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        slider_row.addWidget(self.slider_value)
        layout.addLayout(slider_row)
        layout.addWidget(_gray_label("Higher picks up quieter voices but also more background noise. "
                                     "Lower ignores noise but you need to speak up."))

        layout.addWidget(QLabel("<b>Speed or accuracy</b>"))
        self.quality_box = QComboBox()
        self.quality_box.setAccessibleName("Speech recognition speed or accuracy")
        for label, _model, tip in speech_model.QUALITY_OPTIONS:
            self.quality_box.addItem(label, label)
            self.quality_box.setItemData(self.quality_box.count() - 1, tip, Qt.ToolTipRole)
        self.quality_box.setCurrentIndex(max(0, self.quality_box.findData(speech_model.get_quality())))
        self.quality_box.currentIndexChanged.connect(self._quality_changed)
        layout.addWidget(self.quality_box)
        self.quality_hint = _gray_label(speech_model.quality_hint(self.quality_box.currentData()))
        layout.addWidget(self.quality_hint)

        test_label = QLabel("<b>Test it:</b> talk normally. The bar should turn green and pass the dashed line.")
        test_label.setWordWrap(True)
        layout.addWidget(test_label)
        self.meter = LevelMeter()
        layout.addWidget(self.meter)
        self.meter_status = QLabel()
        self.meter_status.setWordWrap(True)
        self.meter_status.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.meter_status.setMinimumHeight(self.meter_status.fontMetrics().lineSpacing() * 3)
        layout.addWidget(self.meter_status)

        close_btn = QPushButton("Done")
        close_btn.setDefault(True)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)
        close_btn.setFocus()

        self._peak = 0
        self._device_note = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self._sensitivity_changed(self.slider.value())

    def _sensitivity_changed(self, value):
        mic.set_sensitivity(value)
        self.settings.setValue("mic_sensitivity", value)
        self.slider_value.setText(str(value))
        hint = "Custom setting."
        for preset_value, btn in self.preset_buttons.items():
            btn.setChecked(preset_value == value)
            if preset_value == value:
                hint = btn.toolTip()
        self.preset_hint.setText(hint)

    def _quality_changed(self, _index):
        label = self.quality_box.currentData()
        speech_model.set_quality(label)
        self.settings.setValue("dictation_quality", label)
        hint = speech_model.quality_hint(label)
        if dictation.is_voice_active():
            hint += " Takes effect next time you start dictation."
        self.quality_hint.setText(hint)
        speech_model.preload_model()

    def _device_changed(self, _index):
        name = self.device_box.currentData() or ""
        mic.set_device(name)
        self.settings.setValue("mic_device", name)
        self._device_note = dictation.is_voice_active()
        if not self._device_note:
            self.monitor.start(name)

    def _tick(self):
        dictating = dictation.is_voice_active()
        if dictating:
            if self.monitor.running:
                self.monitor.stop()
            level = mic.latest_level
        else:
            self._device_note = False
            if not self.monitor.running and not self.monitor.error:
                self.monitor.start(mic.get_device())
            level = self.monitor.level
        trigger = mic.trigger_level()
        self.meter.set_values(level, trigger)

        self._peak = max(level, self._peak - 2)
        if self.monitor.error and not dictating:
            msg = self.monitor.error
        elif self._peak >= trigger:
            msg = "SharkPad can hear you."
        elif self._peak >= trigger - 15:
            msg = "Almost. Speak a little louder, or move the slider toward High."
        else:
            msg = ("Not hearing speech yet. If you're talking, move the slider toward High "
                   "or pick a different microphone above.")
        if self._device_note:
            msg += "\nThe new microphone will be used the next time you start dictation."
        self.meter_status.setText(msg)

    def showEvent(self, event):
        super().showEvent(event)
        h = self.layout().heightForWidth(self.width())
        if h > 0:
            self.setFixedHeight(h)
        self.monitor.error = ""
        self.timer.start(50)

    def hideEvent(self, event):
        self.timer.stop()
        self.monitor.stop()
        super().hideEvent(event)
