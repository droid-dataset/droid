import time
import threading
import queue
import numpy as np
from collections import deque

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    print("WARNING: pyaudio not available. Microphone recording will be disabled.")
    PYAUDIO_AVAILABLE = False


class MicrophoneReader:
    def __init__(self, sample_rate=44100, chunk_size=1024, channels=1, format_bits=16):
        """
        Initialize microphone reader
        
        Args:
            sample_rate: Audio sample rate (Hz)
            chunk_size: Number of samples per audio chunk
            channels: Number of audio channels (1 for mono, 2 for stereo)
            format_bits: Bit depth (16 or 32)
        """
        if not PYAUDIO_AVAILABLE:
            self.enabled = False
            return
            
        self.enabled = True
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.format_bits = format_bits
        
        # Set PyAudio format
        if format_bits == 16:
            self.format = pyaudio.paInt16
            self.dtype = np.int16
        elif format_bits == 32:
            self.format = pyaudio.paFloat32
            self.dtype = np.float32
        else:
            raise ValueError("format_bits must be 16 or 32")
            
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.recording = False
        self.audio_queue = queue.Queue()
        self.record_thread = None
        
    def start_recording(self):
        """Start recording audio"""
        if not self.enabled:
            return
            
        if self.recording:
            return
            
        try:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            self.recording = True
            self.record_thread = threading.Thread(target=self._record_audio)
            self.record_thread.daemon = True
            self.record_thread.start()
            
        except Exception as e:
            print(f"Failed to start microphone recording: {e}")
            self.enabled = False
            
    def stop_recording(self):
        """Stop recording audio"""
        if not self.enabled or not self.recording:
            return
            
        self.recording = False
        
        if self.record_thread:
            self.record_thread.join(timeout=1.0)
            
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            
    def _record_audio(self):
        """Internal method to record audio in a separate thread"""
        while self.recording:
            try:
                data = self.stream.read(self.chunk_size, exception_on_overflow=False)
                timestamp = time.time_ns()
                audio_array = np.frombuffer(data, dtype=self.dtype)
                
                self.audio_queue.put({
                    'timestamp': timestamp,
                    'data': audio_array,
                    'sample_rate': self.sample_rate,
                    'encoding': f'pcm_{self.format_bits}le'
                })
                
            except Exception as e:
                print(f"Error recording audio: {e}")
                break
                
    def get_audio_data(self):
        """Get the latest audio data"""
        if not self.enabled:
            return None
            
        try:
            return self.audio_queue.get_nowait()
        except queue.Empty:
            return None
            
    def get_all_audio_data(self):
        """Get all available audio data"""
        if not self.enabled:
            return []
            
        audio_data = []
        while True:
            try:
                data = self.audio_queue.get_nowait()
                audio_data.append(data)
            except queue.Empty:
                break
        return audio_data
        
    def is_recording(self):
        """Check if currently recording"""
        return self.recording and self.enabled
        
    def close(self):
        """Clean up resources"""
        self.stop_recording()
        if hasattr(self, 'audio') and self.audio:
            self.audio.terminate() 