# Complete suppression of ALSA/JACK errors
import os
import sys
import warnings

warnings.filterwarnings('ignore')
os.environ['ALSA_CARD'] = 'default'

from PySide6.QtCore import QThread, Signal, QObject
import numpy as np

from collections import deque

# Suppress stderr during audio library imports
_stderr_backup = sys.stderr
sys.stderr = open(os.devnull, 'w')

try:
    # sounddevice ships PortAudio on Windows and macOS, so no compiler is needed
    import sounddevice as sd
    MIC_AVAILABLE = True
except (ImportError, OSError):
    MIC_AVAILABLE = False
finally:
    sys.stderr.close()
    sys.stderr = _stderr_backup

# Microphone capture settings
SAMPLE_RATE = 16000
CHUNK = 1024                      # samples per read (~64 ms)
CHUNK_SECONDS = CHUNK / SAMPLE_RATE
PAUSE_SECONDS = 0.8               # silence that ends a phrase
MIN_PHRASE_SECONDS = 0.3          # ignore clicks/pops shorter than this
MAX_PHRASE_SECONDS = 15           # force transcription of long phrases
PRE_ROLL_SECONDS = 0.5            # audio kept from just before speech starts

# Try to import faster-whisper
try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print("ERROR: faster-whisper not installed. Run: pip install faster-whisper")

class VoiceWorker(QThread):
    text_received = Signal(str)
    error_occurred = Signal(str)
    audio_level = Signal(int)  # Emits 0-100 for mic level
    
    def __init__(self):
        super().__init__()
        self.energy_threshold = 300
        self.running = True

    def set_sensitivity(self, value):
        """Adjust microphone sensitivity (100-4000 range)"""
        self.energy_threshold = value

    def run(self):
        if not WHISPER_AVAILABLE:
            self.error_occurred.emit("faster-whisper not installed")
            return
        if not MIC_AVAILABLE:
            self.error_occurred.emit("sounddevice not installed. Run: pip install sounddevice")
            return
        
        # Suppress ALSA/JACK during microphone operations
        _original_stderr = sys.stderr
        
        try:
            # Load model with visible progress
            sys.stderr = sys.__stderr__
            print("\n=== Loading Whisper Model ===")
            print("This may take a minute on first run (downloading ~150MB)...")
            
            model = WhisperModel("base", device="cpu", compute_type="int8")
            print("Model loaded successfully!\n")
            
            # Now suppress errors for audio operations
            sys.stderr = open(os.devnull, 'w')

            pause_chunks = int(PAUSE_SECONDS / CHUNK_SECONDS)
            min_speech_chunks = int(MIN_PHRASE_SECONDS / CHUNK_SECONDS)
            max_chunks = int(MAX_PHRASE_SECONDS / CHUNK_SECONDS)
            pre_roll = deque(maxlen=int(PRE_ROLL_SECONDS / CHUNK_SECONDS))

            phrase = []
            speech_chunks = 0
            silent_chunks = 0

            with sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1,
                                   dtype='int16', blocksize=CHUNK) as stream:
                print(f"Ready! Sensitivity: {self.energy_threshold}")
                print("Start speaking...")

                while self.running:
                    try:
                        data, _overflowed = stream.read(CHUNK)
                        chunk = np.frombuffer(data, dtype=np.int16)

                        # Monitor audio level (float math avoids int16 overflow)
                        rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                        self.audio_level.emit(min(100, int((rms / 3000) * 100)))

                        loud = rms > self.energy_threshold
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

                        audio_chunks, enough_speech = phrase, speech_chunks >= min_speech_chunks
                        phrase, speech_chunks, silent_chunks = [], 0, 0
                        pre_roll.clear()
                        if not enough_speech:
                            continue

                        audio_float = np.concatenate(audio_chunks).astype(np.float32) / 32768.0

                        # Enhanced transcription settings for better accuracy
                        segments, info = model.transcribe(
                            audio_float,
                            beam_size=5,
                            language="en",
                            condition_on_previous_text=False,
                            vad_filter=True,  # Voice activity detection
                            vad_parameters=dict(
                                threshold=0.5,
                                min_speech_duration_ms=250,
                                min_silence_duration_ms=500
                            )
                        )

                        text = " ".join(seg.text.strip() for seg in segments).strip()
                        if text:
                            self.text_received.emit(text)

                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        # Log individual errors but don't crash
                        sys.stderr = _original_stderr
                        print(f"Recognition error: {e}")
                        sys.stderr = open(os.devnull, 'w')

        except Exception as e:
            sys.stderr = _original_stderr
            self.error_occurred.emit(f"Whisper error: {str(e)}")
            print(f"FATAL ERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if sys.stderr != _original_stderr:
                sys.stderr.close()
            sys.stderr = _original_stderr

    def stop(self):
        self.running = False

_voice_worker_ref = None

def toggle_voice(editor, level_callback=None, sensitivity=300):
    global _voice_worker_ref
    
    if _voice_worker_ref and _voice_worker_ref.isRunning():
        _voice_worker_ref.stop()
        _voice_worker_ref.wait(2000)
        _voice_worker_ref.terminate()
        _voice_worker_ref = None
        print("Voice recognition stopped.")
        return False
    
    _voice_worker_ref = VoiceWorker()
    _voice_worker_ref.energy_threshold = sensitivity
    _voice_worker_ref.text_received.connect(lambda t: editor.insertPlainText(t + " "))
    _voice_worker_ref.error_occurred.connect(lambda e: print(f"Voice error: {e}"))
    
    if level_callback:
        _voice_worker_ref.audio_level.connect(level_callback)
    
    _voice_worker_ref.start(QThread.NormalPriority)
    return True

def set_sensitivity(value):
    """Adjust microphone sensitivity while running"""
    global _voice_worker_ref
    if _voice_worker_ref and _voice_worker_ref.isRunning():
        _voice_worker_ref.set_sensitivity(value)

def is_voice_active():
    global _voice_worker_ref
    return _voice_worker_ref is not None and _voice_worker_ref.isRunning()

def stop_voice():
    global _voice_worker_ref
    if _voice_worker_ref and _voice_worker_ref.isRunning():
        _voice_worker_ref.stop()
        _voice_worker_ref.wait(2000)
        _voice_worker_ref.terminate()
        _voice_worker_ref = None