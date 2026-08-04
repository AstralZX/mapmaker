from PyQt6.QtCore import QObject, pyqtSignal, QUrl, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
import os

class AudioPlayer(QObject):
    positionUpdated = pyqtSignal(int)
    playbackStateChanged = pyqtSignal(bool)
    durationChanged = pyqtSignal(int)
    errorOccurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.playbackStateChanged.connect(self._on_state_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        self.player.errorOccurred.connect(self._on_error)
        
        self.current_file = None
        self.last_position = 0
    
    def load_file(self, filepath):
        if not os.path.exists(filepath):
            self.errorOccurred.emit(f"File not found: {filepath}")
            return False
        
        valid_extensions = ['.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.opus']
        if not any(filepath.lower().endswith(ext) for ext in valid_extensions):
            self.errorOccurred.emit(f"Unsupported file format: {filepath}")
            return False
        
        try:
            url = QUrl.fromLocalFile(filepath)
            self.player.setSource(url)
            self.current_file = filepath
            return True
        except Exception as e:
            self.errorOccurred.emit(f"Failed to load file: {str(e)}")
            return False
    
    def play(self):
        if self.player.source().isEmpty():
            self.errorOccurred.emit("No audio file loaded")
            return
        self.player.play()
    
    def pause(self):
        self.player.pause()
    
    def stop(self):
        self.player.stop()
    
    def get_position(self):
        return self.player.position()
    
    def get_duration(self):
        return self.player.duration()
    
    def set_position(self, position_ms):
        self.player.setPosition(max(0, position_ms))
    
    def is_playing(self):
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    
    def get_volume(self):
        return self.audio_output.volume()
    
    def set_volume(self, volume):
        self.audio_output.setVolume(max(0, min(100, volume)))
    
    def _on_position_changed(self, position):
        self.last_position = position
        self.positionUpdated.emit(position)
    
    def _on_state_changed(self, state):
        is_playing = (state == QMediaPlayer.PlaybackState.PlayingState)
        self.playbackStateChanged.emit(is_playing)
    
    def _on_duration_changed(self, duration):
        self.durationChanged.emit(duration)
    
    def _on_error(self, error, error_string):
        self.errorOccurred.emit(f"Media Error: {error_string}")