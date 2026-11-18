import importlib.util
import os
import threading
import warnings

import numpy as np
from PySide6.QtCore import QThread

warnings.filterwarnings('ignore')

WHISPER_AVAILABLE = importlib.util.find_spec("faster_whisper") is not None
WHISPER_RATE = 16000
QUALITY_OPTIONS = [
    ("Fast", "tiny.en", "Quickest, good for older computers. Makes more mistakes."),
    ("Balanced", "base.en", "Quick and accurate. Best for most computers."),
    ("Accurate", "small.en", "Fewest mistakes, but slower. Needs a fast computer."),
]
DEFAULT_QUALITY = "Balanced"

_quality = DEFAULT_QUALITY
_model = None
_model_name = None
_model_lock = threading.Lock()
_preloader = None


def set_quality(label):
    global _quality
    if label in [q[0] for q in QUALITY_OPTIONS]:
        _quality = label


def get_quality():
    return _quality


def quality_hint(label):
    return next(tip for name, _model, tip in QUALITY_OPTIONS if name == label)


def _wanted_model_name():
    return next(m for label, m, _ in QUALITY_OPTIONS if label == _quality)


def get_model():
    global _model, _model_name
    with _model_lock:
        name = _wanted_model_name()
        if _model is None or _model_name != name:
            from faster_whisper import WhisperModel
            threads = max(1, min(8, (os.cpu_count() or 2) - 1))
            _model = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=threads)
            _model_name = name
        return _model


def model_loaded():
    return _model is not None and _model_name == _wanted_model_name()


class _Preloader(QThread):
    def run(self):
        try:
            get_model()
        except Exception:
            pass


def preload_model():
    """Load the speech model in the background so dictation starts instantly."""
    global _preloader
    if not WHISPER_AVAILABLE or model_loaded() or (_preloader and _preloader.isRunning()):
        return
    _preloader = _Preloader()
    _preloader.start(QThread.LowPriority)


def wait_for_preload(timeout_ms):
    if _preloader is not None:
        _preloader.wait(timeout_ms)


def resample(audio, rate):
    """Linear resample int16 mono audio to 16 kHz float32 in [-1, 1]."""
    audio = audio.astype(np.float32) / 32768.0
    if rate == WHISPER_RATE:
        return audio
    n_out = int(len(audio) * WHISPER_RATE / rate)
    x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def transcribe(model, audio_float):
    """Turn 16 kHz float32 audio into text."""
    segments, _info = model.transcribe(
        audio_float,
        beam_size=1,
        language="en",
        without_timestamps=True,
        condition_on_previous_text=False,
        vad_filter=True,
        vad_parameters=dict(threshold=0.5, min_speech_duration_ms=250, min_silence_duration_ms=500),
    )
    return " ".join(seg.text.strip() for seg in segments).strip()
