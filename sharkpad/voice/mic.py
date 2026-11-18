import math
import os
import sys

import numpy as np

os.environ.setdefault('ALSA_CARD', 'default')
_stderr_backup = sys.stderr
sys.stderr = open(os.devnull, 'w')
try:
    import sounddevice as sd
    MIC_AVAILABLE = True
except (ImportError, OSError):
    sd = None
    MIC_AVAILABLE = False
finally:
    sys.stderr.close()
    sys.stderr = _stderr_backup

CHUNK_SECONDS = 0.05
PRESETS = [
    ("Quiet room", 75, "Library or bedroom. Picks up soft voices."),
    ("Normal", 60, "Classroom or home with a little background noise."),
    ("Noisy room", 40, "Lots of chatter or fan noise. Speak up and close to the mic."),
]
DEFAULT_SENSITIVITY = 60

_sensitivity = DEFAULT_SENSITIVITY
_device_name = ""
latest_level = 0


def set_sensitivity(value):
    """Set sensitivity (0-100). Applies immediately, even while dictating."""
    global _sensitivity
    _sensitivity = max(0, min(100, int(value)))


def get_sensitivity():
    return _sensitivity


def trigger_level():
    """Mic level (0-100) that counts as speech for a given sensitivity."""
    return 100 - _sensitivity


def set_device(name):
    """Choose a microphone by name ("" = system default). Used on the next start."""
    global _device_name
    _device_name = name or ""


def get_device():
    return _device_name


def level_of(chunk):
    return rms_to_level(float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2))))


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
    return None


def open_stream(device_name, callback=None):
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


def friendly_error(e):
    msg = str(e)
    low = msg.lower()
    if "invalid device" in low or "no default input" in low or "device unavailable" in low:
        return "No microphone found. Plug one in, or pick a different one in Voice Dictation Settings."
    if "permission" in low or "not permitted" in low or "access denied" in low:
        return ("SharkPad isn't allowed to use the microphone. Turn on microphone access "
                "for SharkPad in your system's privacy settings.")
    return f"Microphone error: {msg}"


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
            self.level = level_of(indata)

        try:
            self._stream, _rate, _bs = open_stream(device_name, callback)
            self._stream.start()
        except Exception as e:
            self._stream = None
            self.error = friendly_error(e)

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
