import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from typing import Optional
import warnings

# Lightweight deepfake detection using a simple CNN
# that can be loaded with pretrained weights from ASVspoof baseline.
# Falls back to a simple heuristic + random scoring when no model is available
# (useful for demo without heavy model downloads).


class SimpleAntiSpoofCNN(nn.Module):
    """Lightweight CNN for spoof detection. Trained on mel-spectrogram inputs."""

    def __init__(self, n_mels: int = 80, time_frames: int = 200, dropout: float = 0.5):
        super().__init__()
        self.n_mels = n_mels
        self.time_frames = time_frames

        self.conv = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.BatchNorm2d(64), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(64, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
            nn.Conv2d(128, 128, 3, padding=1), nn.BatchNorm2d(128), nn.ReLU(),
            nn.Conv2d(128, 32, 3, padding=1), nn.BatchNorm2d(32), nn.ReLU(),
        )

        # Dynamically compute feature map size
        with torch.no_grad():
            dummy = torch.zeros(1, 1, n_mels, time_frames)
            feat = self.conv(dummy)
            self.feat_dims = feat.numel() // feat.size(0)

        self.pool = nn.AdaptiveAvgPool2d((1, 1))
        self.fc = nn.Sequential(
            nn.Linear(32, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 2)
        )

    def forward(self, x):
        # x: [B, 1, n_mels, time]
        x = self.conv(x)
        x = self.pool(x)
        x = x.view(x.size(0), -1)
        return self.fc(x)


class DeepFakeDetector:
    def __init__(self, model_path: Optional[str] = None, device: str = "cpu"):
        self.device = torch.device(device)
        self.model_loaded = False
        self.model = None

        # Try loading pretrained SpeechBrain model if available
        try:
            from speechbrain.inference.AntiSpoofing import AntiSpoofing
            if model_path:
                self.model = AntiSpoofing.from_hparams(
                    source=model_path, run_opts={"device": device}
                )
                self.model_loaded = True
                print(f"Loaded deepfake model from {model_path}")
        except Exception as e:
            warnings.warn(f"Could not load pretrained deepfake model: {e}. Using heuristic fallback.")
            self.model_loaded = False

    def score(self, audio: torch.Tensor, sr: int = 16000) -> float:
        """Return deepfake probability (0 = real, 1 = fake)."""
        if not self.model_loaded or self.model is None:
            # Heuristic fallback based on audio characteristics
            return self._heuristic_score(audio)

        try:
            # Use the pretrained model directly
            # SpeechBrain anti-spoofing returns etiher a spoof score or classification
            if hasattr(self.model, 'classify_batch'):
                pred, score = self.model.classify_batch(audio)
                # Try to get a probability
                if isinstance(score, torch.Tensor):
                    return float(score.item())
                return 0.5
            elif hasattr(self.model, 'classify_file'):
                pred, score = self.model.classify_file(audio)
                return float(score) if isinstance(score, (int, float)) else 0.5
            else:
                return self._heuristic_score(audio)
        except Exception as e:
            warnings.warn(f"Model inference failed: {e}, using heuristic.")
            return self._heuristic_score(audio)

    def _heuristic_score(self, audio: torch.Tensor) -> float:
        """Heuristic fallback scoring based on audio characteristics."""
        # Real speech: more natural variation, higher entropy
        # Synthetic speech: more consistent spectral structure, lower entropy
        audio_np = audio.numpy() if isinstance(audio, torch.Tensor) else audio
        if audio_np.ndim > 1:
            audio_np = audio_np.squeeze()

        # Frame-level features
        frame_size = int(0.025 * sr)  # 25ms frames
        hop = int(0.01 * sr)  # 10ms hop
        frames = []
        for i in range(0, len(audio_np) - frame_size, hop):
            frame = audio_np[i:i + frame_size]
            if len(frame) == frame_size:
                frames.append(frame)

        if len(frames) < 10:
            return 0.3  # Not enough data

        frames = np.array(frames)

        # Zero-crossing rate instability (real speech has more variability)
        zcrs = []
        for frame in frames:
            zc = np.sum(np.diff(np.sign(frame))) / len(frame)
            zcrs.append(abs(zc))
        zcr_std = np.std(zcrs)

        # Spectral centroid variation
        ffts = []
        for frame in frames:
            fft = np.abs(np.fft.rfft(frame))
            ffts.append(fft)
        ffts = np.array(ffts)
        spectral_std = np.std(np.mean(ffts, axis=1))

        # Real: more variation; synthetic: flatter
        # Normalize to roughly 0-1 using thresholds
        score = 0.5 - (zcr_std * 0.5) - (spectral_std * 0.001)
        score = max(0.0, min(score, 1.0))
        return score
