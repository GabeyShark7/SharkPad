# Complete suppression of ALSA/JACK errors
import os
import sys
import warnings

warnings.filterwarnings('ignore')
os.environ['ALSA_CARD'] = 'default'

from PySide6.QtCore import QThread, Signal, QObject
import numpy as np

# Suppress stderr during audio library imports
_stderr_backup = sys.stderr
sys.stderr = open(os.devnull, 'w')

try:
    import speech_recognition as sr
finally:
    sys.stderr.close()
    sys.stderr = _stderr_backup

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
            
            r = sr.Recognizer()
            r.energy_threshold = self.energy_threshold
            r.dynamic_energy_threshold = False  # Manual control for better accuracy
            r.pause_threshold = 0.8  # Shorter pause for better responsiveness
            r.phrase_threshold = 0.3
            r.non_speaking_duration = 0.5
            
            mic = sr.Microphone(sample_rate=16000)
            
            with mic as src:
                print("Adjusting for background noise...")
                r.adjust_for_ambient_noise(src, duration=2)
                print(f"Ready! Sensitivity: {self.energy_threshold}")
                print("Start speaking...")
                
                while self.running:
                    try:
                        # Monitor audio level
                        audio_data = src.stream.read(1024)
                        audio_array = np.frombuffer(audio_data, dtype=np.int16)
                        rms = np.sqrt(np.mean(audio_array**2))
                        level = min(100, int((rms / 3000) * 100))
                        self.audio_level.emit(level)
                        
                        # Listen for speech with updated threshold
                        r.energy_threshold = self.energy_threshold
                        audio = r.listen(src, timeout=0.5, phrase_time_limit=15)
                        
                        # Convert to numpy array
                        raw_data = audio.get_raw_data()
                        audio_array = np.frombuffer(raw_data, dtype=np.int16)
                        audio_float = audio_array.astype(np.float32) / 32768.0
                        
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
                        
                        # Collect text from segments
                        text_parts = []
                        for segment in segments:
                            text_parts.append(segment.text.strip())
                        
                        text = " ".join(text_parts).strip()
                        
                        if text and len(text) > 0:
                            self.text_received.emit(text)
                            
                    except sr.WaitTimeoutError:
                        # Normal timeout, continue listening
                        continue
                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        # Log individual errors but don't crash
                        if "timeout" not in str(e).lower():
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