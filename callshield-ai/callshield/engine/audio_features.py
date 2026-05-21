"""CallShield Audio Feature Extraction (v2.3.3).

Standardized audio processing for deepfake detection:
- 16 kHz mono conversion
- 4-second chunking/padding
- Log-mel spectrogram extraction
"""

import numpy as np

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    librosa = None
    LIBROSA_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    TORCH_AVAILABLE = False

AUDIO_LIBS_AVAILABLE = LIBROSA_AVAILABLE and TORCH_AVAILABLE

from pathlib import Path
from typing import Union


class AudioFeatureExtractor:
    """Extracts log-mel spectrograms from audio for ML models."""

    def __init__(self, 
                 sample_rate: int = 16000, 
                 duration: int = 4, 
                 n_mels: int = 128,
                 n_fft: int = 1024,
                 hop_length: int = 256,
                 normalization: str = "zscore"):
        self.sample_rate = sample_rate
        self.duration = duration
        self.n_mels = n_mels
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.target_samples = sample_rate * duration
        self.normalization = normalization

    def load_audio(self, audio_path: Union[str, Path]) -> np.ndarray:
        """Load, resample, and convert to mono."""
        if not LIBROSA_AVAILABLE:
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
        if not LIBROSA_AVAILABLE:
            raise ImportError("librosa not found. Spectrogram extraction unavailable.")
        mel = librosa.feature.melspectrogram(
            y=y, 
            sr=self.sample_rate, 
            n_fft=self.n_fft, 
            hop_length=self.hop_length, 
            n_mels=self.n_mels
        )
        log_mel = librosa.power_to_db(mel, ref=np.max)

        if self.normalization == "zscore":
            log_mel = (log_mel - log_mel.mean()) / (log_mel.std() + 1e-6)
        elif self.normalization == "minmax":
            log_mel = np.clip(log_mel, -80.0, 0.0)
            log_mel = (log_mel + 80.0) / 80.0
        else:
            raise ValueError(f"Unsupported mel normalization: {self.normalization}")
        return log_mel

    def to_tensor(self, log_mel: np.ndarray) -> 'torch.Tensor':
        """Convert to PyTorch tensor with channel dimension [1, 1, n_mels, time]."""
        if not TORCH_AVAILABLE:
            raise ImportError("torch not found. Tensor conversion unavailable.")
        import torch
        tensor = torch.from_numpy(log_mel).float()
        return tensor.unsqueeze(0).unsqueeze(0)
