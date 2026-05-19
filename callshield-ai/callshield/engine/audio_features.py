"""CallShield Audio Feature Extraction (v2.3).

Standardized audio processing for deepfake detection:
- 16 kHz mono conversion
- 4-second chunking/padding
- Log-mel spectrogram extraction
"""

try:
    import numpy as np
    import librosa
    import torch
    AUDIO_LIBS_AVAILABLE = True
except ImportError:
    AUDIO_LIBS_AVAILABLE = False
    import numpy as np # Still needed for basic arrays

from pathlib import Path
from typing import Optional, Union
import warnings


class AudioFeatureExtractor:
    """Extracts log-mel spectrograms from audio for ML models."""

    def __init__(self, 
                 sample_rate: int = 16000, 
                 duration: int = 4, 
                 n_mels: int = 128,
                 n_fft: int = 1024,
                 hop_length: int = 256):
        self.sample_rate = sample_rate
        self.duration = duration
        self.n_mels = n_mels
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.target_samples = sample_rate * duration

    def load_audio(self, audio_path: Union[str, Path]) -> np.ndarray:
        """Load, resample, and convert to mono."""
        if not AUDIO_LIBS_AVAILABLE:
            raise ImportError("librosa not found. Audio loading unavailable.")
        y, sr = librosa.load(audio_path, sr=self.sample_rate, mono=True)
        return y

    def preprocess_audio(self, y: np.ndarray) -> np.ndarray:
        """Trim or pad to exact duration."""
        if len(y) > self.target_samples:
            # Center crop
            start = (len(y) - self.target_samples) // 2
            y = y[start:start + self.target_samples]
        else:
            # Zero pad
            padding = self.target_samples - len(y)
            y = np.pad(y, (0, padding), mode='constant')
        return y

    def extract_mel(self, y: np.ndarray) -> np.ndarray:
        """Extract log-mel spectrogram."""
        if not AUDIO_LIBS_AVAILABLE:
            raise ImportError("librosa not found. Spectrogram extraction unavailable.")
        mel = librosa.feature.melspectrogram(
            y=y, 
            sr=self.sample_rate, 
            n_fft=self.n_fft, 
            hop_length=self.hop_length, 
            n_mels=self.n_mels
        )
        log_mel = librosa.power_to_db(mel, ref=np.max)
        
        # Normalize to -1 to 1 range (approx)
        log_mel = (log_mel + 40.0) / 40.0
        return log_mel

    def to_tensor(self, log_mel: np.ndarray) -> 'torch.Tensor':
        """Convert to PyTorch tensor with channel dimension [1, 1, n_mels, time]."""
        if not AUDIO_LIBS_AVAILABLE:
            raise ImportError("torch not found. Tensor conversion unavailable.")
        import torch
        tensor = torch.from_numpy(log_mel).float()
        return tensor.unsqueeze(0).unsqueeze(0)
