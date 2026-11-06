# Voice dictation for SharkPad: microphone capture (sounddevice) + offline
# speech-to-text (faster-whisper). Works on Windows, macOS and Linux.

import math
import os
import sys
import threading
import warnings
from collections import deque

warnings.filterwarnings('ignore')
os.environ.setdefault('ALSA_CARD', 'default')

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot

# Suppress stderr noise from audio library imports
_stderr_backup = sys.stderr
sys.stderr = open(os.devnull, 'w')
try:
    # sounddevice ships PortAudio on Windows and macOS; Linux needs libportaudio2
    import sounddevice as sd
    MIC_AVAILABLE = True
except (ImportError, OSError):
    sd = None
    MIC_AVAILABLE = False
finally:
    sys.stderr.close()
    sys.stderr = _stderr_backup

# faster-whisper is heavy to import, so only check it's installed here and
# import it when the speech model is first needed
import importlib.util
WHISPER_AVAILABLE = importlib.util.find_spec("faster_whisper") is not None


WHISPER_RATE = 16000              # Whisper expects 16 kHz mono
CHUNK_SECONDS = 0.05              # mic read size (50 ms)
PAUSE_SECONDS = 0.6               # silence that ends a phrase
MIN_PHRASE_SECONDS = 0.3          # ignore clicks/pops shorter than this
MAX_PHRASE_SECONDS = 15           # force transcription of long phrases
PRE_ROLL_SECONDS = 0.4            # audio kept from just before speech starts

# Sensitivity is 0-100: higher = picks up quieter speech.
# Presets shown in the settings dialog: (label, value, description)
PRESETS = [
    ("Quiet room", 75, "Library or bedroom. Picks up soft voices."),
    ("Normal", 60, "Classroom or home with a little background noise."),
    ("Noisy room", 40, "Lots of chatter or fan noise. Speak up and close to the mic."),
]
DEFAULT_SENSITIVITY = 60

_sensitivity = DEFAULT_SENSITIVITY
_device_name = ""                 # "" = system default microphone
latest_level = 0                  # last mic level (0-100) seen by the dictation worker


def set_sensitivity(value):
    """Set sensitivity (0-100). Applies immediately, even while dictating."""
    global _sensitivity
    _sensitivity = max(0, min(100, int(value)))


def get_sensitivity():
    return _sensitivity


def trigger_level(sensitivity=None):
    """Mic level (0-100) that counts as speech for a given sensitivity."""
    s = _sensitivity if sensitivity is None else sensitivity
    return 100 - s


def set_device(name):
    """Choose a microphone by name ("" = system default). Used on the next start."""
    global _device_name
    _device_name = name or ""


def get_device():
    return _device_name


def rms_to_level(rms):
    """Convert int16 RMS to a 0-100 meter level on a -60..0 dBFS scale.

    A decibel scale makes quiet and loud microphones both move the meter
    in a useful range, on every platform.
    """
    if rms <= 0:
        return 0
    db = 20 * math.log10(rms / 32768.0)
    return int(max(0, min(100, (db + 60) / 60 * 100)))


def list_input_devices():
    """Names of microphones on the default audio system, without duplicates."""
    if not MIC_AVAILABLE:
        return []
    try:
        default_api = sd.default.hostapi
        names = []
        for d in sd.query_devices():
            if d['max_input_channels'] > 0 and d['hostapi'] == default_api and d['name'] not in names:
                names.append(d['name'])
        return names
    except Exception:
        return []


def _resolve_device(name):
    """Turn a saved microphone name into a sounddevice index (None = default)."""
    if not name:
        return None
    try:
        default_api = sd.default.hostapi
        for i, d in enumerate(sd.query_devices()):
            if d['max_input_channels'] > 0 and d['name'] == name and d['hostapi'] == default_api:
                return i
    except Exception:
        pass
    return None  # saved mic was unplugged: fall back to the default


def _open_stream(device_name, callback=None):
    """Open a mono int16 input stream at the device's own sample rate.

    Many Mac and Linux microphones reject 16 kHz, so we record at the native
    rate and resample to 16 kHz ourselves.
    """
    device = _resolve_device(device_name)
    info = sd.query_devices(device, 'input')
    rate = int(info['default_samplerate']) or 48000
    blocksize = int(rate * CHUNK_SECONDS)
    stream_cls = sd.InputStream if callback else sd.RawInputStream
    stream = stream_cls(device=device, samplerate=rate, channels=1, dtype='int16',
                        blocksize=blocksize, callback=callback)
    return stream, rate, blocksize


def _resample(audio, rate):
    """Linear resample int16 mono audio to 16 kHz float32 in [-1, 1]."""
    audio = audio.astype(np.float32) / 32768.0
    if rate == WHISPER_RATE:
        return audio
    n_out = int(len(audio) * WHISPER_RATE / rate)
    x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def _friendly_error(e):
    msg = str(e)
    low = msg.lower()
    if "invalid device" in low or "no default input" in low or "device unavailable" in low:
        return "No microphone found. Plug one in, or pick a different one in Voice Dictation Settings."
    if "permission" in low or "not permitted" in low or "access denied" in low:
        return ("SharkPad isn't allowed to use the microphone. Turn on microphone access "
                "for SharkPad in your system's privacy settings.")
    return f"Microphone error: {msg}"


# Speech model choices: (label, Whisper model, description). English-only
# models are faster and more accurate for English than the multilingual ones.
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


def set_quality(label):
    global _quality
    if label in [q[0] for q in QUALITY_OPTIONS]:
        _quality = label


def get_quality():
    return _quality


def _wanted_model_name():
    return next(m for label, m, _ in QUALITY_OPTIONS if label == _quality)


def _get_model():
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
            _get_model()
        except Exception:
            pass  # a real error is reported when dictation starts


_preloader = None


def preload_model():
    """Load the speech model in the background so dictation starts instantly."""
    global _preloader
    if not WHISPER_AVAILABLE or model_loaded() or (_preloader and _preloader.isRunning()):
        return
    _preloader = _Preloader()
    _preloader.start(QThread.LowPriority)


class VoiceWorker(QThread):
    text_received = Signal(str)
    error_occurred = Signal(str)
    status_changed = Signal(str)

    def __init__(self, device_name=""):
        super().__init__()
        self.device_name = device_name
        self.running = True

    def run(self):
        global latest_level
        if not MIC_AVAILABLE:
            hint = " On Linux also run: sudo apt install libportaudio2" if sys.platform.startswith("linux") else ""
            self.error_occurred.emit("Microphone support isn't installed. Run: pip install sounddevice." + hint)
            return
        if not WHISPER_AVAILABLE:
            self.error_occurred.emit("Speech recognition isn't installed. Run: pip install faster-whisper")
            return

        try:
            if not model_loaded():
                self.status_changed.emit("Getting the speech model ready (the first time it downloads, which takes a minute)...")
            model = _get_model()
        except Exception as e:
            self.error_occurred.emit(f"Couldn't load the speech model: {e}")
            return
        if not self.running:
            return

        try:
            stream, rate, blocksize = _open_stream(self.device_name)
        except Exception as e:
            self.error_occurred.emit(_friendly_error(e))
            return

        chunks_per_sec = rate / blocksize
        pause_chunks = int(PAUSE_SECONDS * chunks_per_sec)
        min_speech_chunks = max(1, int(MIN_PHRASE_SECONDS * chunks_per_sec))
        max_chunks = int(MAX_PHRASE_SECONDS * chunks_per_sec)
        pre_roll = deque(maxlen=max(1, int(PRE_ROLL_SECONDS * chunks_per_sec)))

        phrase, speech_chunks, silent_chunks = [], 0, 0
        self.status_changed.emit("Listening... speak now")

        try:
            with stream:
                while self.running:
                    data, _overflowed = stream.read(blocksize)
                    chunk = np.frombuffer(data, dtype=np.int16).copy()

                    rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                    level = rms_to_level(rms)
                    latest_level = level
                    loud = level >= trigger_level()

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
                    # The quiet tail of this phrase may hold the soft start of the next word
                    pre_roll.clear()
                    pre_roll.extend(phrase[-pre_roll.maxlen:])
                    phrase, speech_chunks, silent_chunks = [], 0, 0
                    if not enough_speech:
                        continue

                    self.status_changed.emit("Writing what you said...")
                    text = transcribe(model, _resample(audio, rate))
                    if text:
                        self.text_received.emit(text)
                    if self.running:
                        self.status_changed.emit("Listening... speak now")
        except Exception as e:
            if self.running:
                self.error_occurred.emit(_friendly_error(e))
        finally:
            latest_level = 0

    def stop(self):
        self.running = False


def transcribe(model, audio_float):
    """Turn 16 kHz float32 audio into text."""
    segments, _info = model.transcribe(
        audio_float,
        beam_size=1,              # greedy decoding: several times faster, near-identical for dictation
        language="en",
        without_timestamps=True,
        condition_on_previous_text=False,
        vad_filter=True,  # drops non-speech that slipped past the threshold
        vad_parameters=dict(threshold=0.5, min_speech_duration_ms=250, min_silence_duration_ms=500),
    )
    return " ".join(seg.text.strip() for seg in segments).strip()


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


_voice_worker_ref = None
_live_threads = {}                # worker -> bridge, kept alive until the thread finishes


def _forget(worker):
    _live_threads.pop(worker, None)


def start_voice(editor, on_status=None, on_error=None, on_stopped=None):
    """Start dictation into `editor`. Callbacks run on the UI thread."""
    global _voice_worker_ref
    if is_voice_active():
        return True

    def insert_text(t):
        editor.insertPlainText(t + " ")

    def stopped():
        global _voice_worker_ref
        if _voice_worker_ref is worker:
            _voice_worker_ref = None
        _forget(worker)
        if on_stopped:
            on_stopped()

    worker = VoiceWorker(_device_name)
    bridge = _UiBridge(
        insert_text,
        on_error or (lambda e: print(f"Voice error: {e}")),
        on_status or (lambda s: None),
        stopped,
    )
    worker.text_received.connect(bridge.text)
    worker.error_occurred.connect(bridge.error)
    worker.status_changed.connect(bridge.status)
    worker.finished.connect(bridge.stopped)
    _live_threads[worker] = bridge
    _voice_worker_ref = worker
    worker.start()
    return True


def stop_voice():
    """Stop dictation. A phrase already being written still gets inserted."""
    global _voice_worker_ref
    worker = _voice_worker_ref
    _voice_worker_ref = None
    if worker is not None:
        worker.stop()


def toggle_voice(editor, on_status=None, on_error=None, on_stopped=None):
    """Turn dictation on or off. Returns True if it is now on."""
    if is_voice_active():
        stop_voice()
        return False
    return start_voice(editor, on_status, on_error, on_stopped)


def is_voice_active():
    return _voice_worker_ref is not None and _voice_worker_ref.isRunning()


def wait_for_shutdown(timeout_ms=5000):
    """Call on app exit so no audio thread is left running."""
    stop_voice()
    for w in list(_live_threads):
        w.stop()
        w.wait(timeout_ms)
    if _preloader is not None:
        _preloader.wait(timeout_ms)


class MicMonitor:
    """Opens the mic just to measure its level, for the settings meter."""

    def __init__(self):
        self.level = 0
        self.error = ""
        self._stream = None

    def start(self, device_name):
        self.stop()
        self.error = ""
        if not MIC_AVAILABLE:
            self.error = "Microphone support isn't installed (pip install sounddevice)."
            return

        def callback(indata, frames, time_info, status):
            rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2)))
            self.level = rms_to_level(rms)

        try:
            self._stream, _rate, _bs = _open_stream(device_name, callback)
            self._stream.start()
        except Exception as e:
            self._stream = None
            self.error = _friendly_error(e)

    def stop(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.level = 0

    @property
    def running(self):
        return self._stream is not None
