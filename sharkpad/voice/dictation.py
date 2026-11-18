import sys
from collections import deque

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot

from sharkpad.editor.text_tools import insert_as_own_step
from sharkpad.voice import mic, speech_model

PAUSE_SECONDS = 0.6
MIN_PHRASE_SECONDS = 0.3
MAX_PHRASE_SECONDS = 15
PRE_ROLL_SECONDS = 0.4


class VoiceWorker(QThread):
    text_received = Signal(str)
    error_occurred = Signal(str)
    status_changed = Signal(str)

    def __init__(self, device_name=""):
        super().__init__()
        self.device_name = device_name
        self.running = True

    def run(self):
        if not mic.MIC_AVAILABLE:
            hint = " On Linux also run: sudo apt install libportaudio2" if sys.platform.startswith("linux") else ""
            self.error_occurred.emit("Microphone support isn't installed. Run: pip install sounddevice." + hint)
            return
        if not speech_model.WHISPER_AVAILABLE:
            self.error_occurred.emit("Speech recognition isn't installed. Run: pip install faster-whisper")
            return

        try:
            if not speech_model.model_loaded():
                self.status_changed.emit("Getting the speech model ready (the first time it downloads, which takes a minute)...")
            model = speech_model.get_model()
        except Exception as e:
            self.error_occurred.emit(f"Couldn't load the speech model: {e}")
            return
        if not self.running:
            return

        try:
            stream, rate, blocksize = mic.open_stream(self.device_name)
        except Exception as e:
            self.error_occurred.emit(mic.friendly_error(e))
            return

        try:
            with stream:
                self._listen(stream, rate, blocksize, model)
        except Exception as e:
            if self.running:
                self.error_occurred.emit(mic.friendly_error(e))
        finally:
            mic.latest_level = 0

    def _listen(self, stream, rate, blocksize, model):
        chunks_per_sec = rate / blocksize
        pause_chunks = int(PAUSE_SECONDS * chunks_per_sec)
        min_speech_chunks = max(1, int(MIN_PHRASE_SECONDS * chunks_per_sec))
        max_chunks = int(MAX_PHRASE_SECONDS * chunks_per_sec)
        pre_roll = deque(maxlen=max(1, int(PRE_ROLL_SECONDS * chunks_per_sec)))

        phrase, speech_chunks, silent_chunks = [], 0, 0
        self.status_changed.emit("Listening... speak now")

        while self.running:
            data, _overflowed = stream.read(blocksize)
            chunk = np.frombuffer(data, dtype=np.int16).copy()

            level = mic.level_of(chunk)
            mic.latest_level = level
            loud = level >= mic.trigger_level()

            if not phrase:
                if loud:
                    phrase = list(pre_roll) + [chunk]
                    speech_chunks, silent_chunks = 1, 0
                else:
                    pre_roll.append(chunk)
                continue

            phrase.append(chunk)
            if loud:
                speech_chunks += 1
                silent_chunks = 0
            else:
                silent_chunks += 1

            if silent_chunks < pause_chunks and len(phrase) < max_chunks:
                continue

            audio, enough_speech = np.concatenate(phrase), speech_chunks >= min_speech_chunks
            pre_roll.clear()
            pre_roll.extend(phrase[-pre_roll.maxlen:])
            phrase, speech_chunks, silent_chunks = [], 0, 0
            if not enough_speech:
                continue

            self.status_changed.emit("Writing what you said...")
            text = speech_model.transcribe(model, speech_model.resample(audio, rate))
            if text:
                self.text_received.emit(text)
            if self.running:
                self.status_changed.emit("Listening... speak now")

    def stop(self):
        self.running = False


class _UiBridge(QObject):
    """Lives on the UI thread so worker signals are delivered there.

    Qt widgets may only be touched from the UI thread; connecting worker
    signals to this object's slots makes Qt queue them safely.
    """

    def __init__(self, on_text, on_error, on_status, on_stopped):
        super().__init__()
        self._on_text, self._on_error = on_text, on_error
        self._on_status, self._on_stopped = on_status, on_stopped

    @Slot(str)
    def text(self, t):
        self._on_text(t)

    @Slot(str)
    def error(self, e):
        self._on_error(e)

    @Slot(str)
    def status(self, s):
        self._on_status(s)

    @Slot()
    def stopped(self):
        self._on_stopped()


_active_worker = None
_live_threads = {}


def start_voice(editor, on_status, on_error, on_stopped):
    """Start dictation into `editor`. Callbacks run on the UI thread."""
    global _active_worker

    def stopped():
        global _active_worker
        if _active_worker is worker:
            _active_worker = None
        _live_threads.pop(worker, None)
        on_stopped()

    worker = VoiceWorker(mic.get_device())
    bridge = _UiBridge(lambda t: insert_as_own_step(editor, t + " "), on_error, on_status, stopped)
    worker.text_received.connect(bridge.text)
    worker.error_occurred.connect(bridge.error)
    worker.status_changed.connect(bridge.status)
    worker.finished.connect(bridge.stopped)
    _live_threads[worker] = bridge
    _active_worker = worker
    worker.start()


def stop_voice():
    """Stop dictation. A phrase already being written still gets inserted."""
    global _active_worker
    worker = _active_worker
    _active_worker = None
    if worker is not None:
        worker.stop()


def toggle_voice(editor, on_status, on_error, on_stopped):
    """Turn dictation on or off. Returns True if it is now on."""
    if is_voice_active():
        stop_voice()
        return False
    start_voice(editor, on_status, on_error, on_stopped)
    return True


def is_voice_active():
    return _active_worker is not None and _active_worker.isRunning()


def wait_for_shutdown(timeout_ms=5000):
    """Call on app exit so no audio thread is left running."""
    stop_voice()
    for w in list(_live_threads):
        w.stop()
        w.wait(timeout_ms)
    speech_model.wait_for_preload(timeout_ms)
