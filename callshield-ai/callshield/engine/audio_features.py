"""CallShield Audio Feature Extraction (v2.3.5).

Standardized audio processing for deepfake detection:
- 16 kHz mono conversion
- 4-second chunking/padding
- Log-mel spectrogram extraction
"""

import base64
import os
import tempfile
from io import BytesIO

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
from typing import Iterator, Union


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

    def has_speech(self, y: np.ndarray, min_rms: float = 0.008, min_peak: float = 0.03) -> bool:
        """Return whether an audio vector has enough signal to run inference."""
        return self.audio_activity(y, min_rms=min_rms, min_peak=min_peak)["speech_like"]

    def audio_activity(
        self,
        y: np.ndarray,
        min_rms: float = 0.008,
        min_peak: float = 0.03,
        min_active_ratio: float = 0.03,
    ) -> dict:
        """Measure whether audio contains enough speech-like activity.

        This is deliberately conservative for live phone chunks. Very low-level
        room noise can cause Whisper hallucinations and CNN false positives, so
        quiet chunks are treated as no-speech before ASR/deepfake fusion.
        """
        if y is None:
            return {
                "speech_like": False,
                "duration_seconds": 0.0,
                "rms": 0.0,
                "peak": 0.0,
                "active_ratio": 0.0,
                "rms_dbfs": -120.0,
            }
        samples = np.asarray(y, dtype=np.float32)
        if samples.size == 0:
            return {
                "speech_like": False,
                "duration_seconds": 0.0,
                "rms": 0.0,
                "peak": 0.0,
                "active_ratio": 0.0,
                "rms_dbfs": -120.0,
            }
        rms = float(np.sqrt(np.mean(np.square(samples))))
        peak = float(np.max(np.abs(samples)))
        frame_length = max(1, int(self.sample_rate * 0.03))
        hop_length = max(1, frame_length // 2)
        frame_rms = []
        for start in range(0, max(1, samples.size - frame_length + 1), hop_length):
            frame = samples[start:start + frame_length]
            if frame.size:
                frame_rms.append(float(np.sqrt(np.mean(np.square(frame)))))
        active_ratio = float(np.mean(np.asarray(frame_rms) >= min_rms)) if frame_rms else 0.0
        rms_dbfs = float(20.0 * np.log10(max(rms, 1e-6)))
        return {
            "speech_like": bool(rms >= min_rms and peak >= min_peak and active_ratio >= min_active_ratio),
            "duration_seconds": round(float(samples.size / self.sample_rate), 3),
            "rms": round(rms, 6),
            "peak": round(peak, 6),
            "active_ratio": round(active_ratio, 3),
            "rms_dbfs": round(rms_dbfs, 1),
        }

    def iter_windows(self, y: np.ndarray, hop_seconds: float = 2.0) -> Iterator[np.ndarray]:
        """Yield fixed-length windows so long calls are not reduced to one center crop."""
        samples = np.asarray(y, dtype=np.float32)
        if len(samples) <= self.target_samples:
            yield self.preprocess_audio(samples)
            return

        hop_samples = max(1, int(self.sample_rate * hop_seconds))
        last_start = len(samples) - self.target_samples
        starts = list(range(0, last_start + 1, hop_samples))
        if starts[-1] != last_start:
            starts.append(last_start)

        for start in starts:
            yield samples[start:start + self.target_samples]

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

    def spectrogram_preview(self, y: np.ndarray, max_width: int = 520) -> dict:
        """Return a compact PNG preview of the log-mel spectrogram for UI debugging."""
        if not LIBROSA_AVAILABLE:
            return {
                "available": False,
                "error": "librosa not found. Spectrogram preview unavailable.",
            }

        samples = self.preprocess_audio(np.asarray(y, dtype=np.float32))
        mel = librosa.feature.melspectrogram(
            y=samples,
            sr=self.sample_rate,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            n_mels=self.n_mels,
        )
        log_mel = librosa.power_to_db(mel, ref=np.max)
        clipped = np.clip(log_mel, -80.0, 0.0)

        mpl_config = Path(
            os.environ.get(
                "CALLSHIELD_MPLCONFIGDIR",
                str(Path(tempfile.gettempdir()) / "callshield-matplotlib"),
            )
        )
        mpl_config.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(mpl_config))

        import matplotlib
        matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt

        width = max(3.2, min(6.5, max_width / 100.0))
        height = 2.2
        fig, ax = plt.subplots(figsize=(width, height), dpi=100)
        ax.imshow(clipped, aspect="auto", origin="lower", cmap="magma", vmin=-80.0, vmax=0.0)
        ax.axis("off")
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

        buffer = BytesIO()
        fig.savefig(buffer, format="png", bbox_inches="tight", pad_inches=0)
        plt.close(fig)
        image_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")

        return {
            "available": True,
            "content_type": "image/png",
            "image_base64": image_base64,
            "normalization": "db_clipped_-80_0",
            "n_mels": int(self.n_mels),
            "frames": int(clipped.shape[1]),
            "sample_rate": int(self.sample_rate),
            "duration_seconds": round(float(samples.size / self.sample_rate), 3),
        }

    def to_tensor(self, log_mel: np.ndarray) -> 'torch.Tensor':
        """Convert to PyTorch tensor with channel dimension [1, 1, n_mels, time]."""
        if not TORCH_AVAILABLE:
            raise ImportError("torch not found. Tensor conversion unavailable.")
        import torch
        tensor = torch.from_numpy(log_mel).float()
        return tensor.unsqueeze(0).unsqueeze(0)
