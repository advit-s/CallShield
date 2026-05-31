"""CallShield Deepfake Detection Engine (v2.3.5).

CNN-based architecture for synthetic speech detection.
Uses log-mel spectrograms as input.
"""

import json
import warnings
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from .audio_features import AudioFeatureExtractor, LIBROSA_AVAILABLE

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    # Define dummy classes if torch is missing to avoid name errors during class definition
    class nn:
        class Module: pass
        class Conv2d: pass
        class BatchNorm2d: pass
        class MaxPool2d: pass
        class AdaptiveAvgPool2d: pass
        class Dropout: pass
        class Linear: pass
        class Sigmoid: pass
    class F:
        @staticmethod
        def relu(x): return x


class DeepFakeCNN(nn.Module):
    """Small, efficient CNN for deepfake detection."""
    def __init__(self, n_mels=128):
        if not TORCH_AVAILABLE:
            super().__init__()
            return
            
        super(DeepFakeCNN, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, kernel_size=3, stride=1, padding=1)
        self.bn1 = nn.BatchNorm2d(32)
        self.pool1 = nn.MaxPool2d(kernel_size=2, stride=2)
        
        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1)
        self.bn2 = nn.BatchNorm2d(64)
        self.pool2 = nn.MaxPool2d(kernel_size=2, stride=2)
        
        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1)
        self.bn3 = nn.BatchNorm2d(128)
        self.pool3 = nn.MaxPool2d(kernel_size=2, stride=2)
        self.global_pool = nn.AdaptiveAvgPool2d((1, 1))

        self.dropout = nn.Dropout(0.3)

        self.fc1 = nn.Linear(128, 64)
        self.fc2 = nn.Linear(64, 1)
        self.sigmoid = nn.Sigmoid()

    def forward_logits(self, x):
        if not TORCH_AVAILABLE:
            return x
        x = self.pool1(F.relu(self.bn1(self.conv1(x))))
        x = self.pool2(F.relu(self.bn2(self.conv2(x))))
        x = self.pool3(F.relu(self.bn3(self.conv3(x))))
        x = self.global_pool(x)
        x = torch.flatten(x, 1)
        x = self.dropout(F.relu(self.fc1(x)))
        return self.fc2(x)

    def forward(self, x):
        if not TORCH_AVAILABLE:
            return x
        return self.sigmoid(self.forward_logits(x))


class DeepFakeDetector:
    """Inference engine for deepfake detection."""

    def __init__(self, model_path: Optional[str] = None, calibration_path: Optional[str] = None):
        self.extractor = AudioFeatureExtractor()
        self.checkpoint_path = Path(model_path) if model_path else self._default_checkpoint_path()
        self.calibration_path = Path(calibration_path) if calibration_path else self._calibration_path_for_checkpoint(self.checkpoint_path)
        self.model = None
        self.model_status = "pipeline_implemented_no_trained_model"
        self.calibration_status = "uncalibrated"
        self.operating_threshold = 0.5
        self.soft_audio_threshold = 0.2
        self.hard_audio_threshold = 0.5
        self.target_fpr = None
        self.calibration_note = "No calibrated threshold file found."
        self.device = "cpu"

        if not self.checkpoint_path.exists():
            return

        if not TORCH_AVAILABLE:
            self.model_status = "audio_libraries_unavailable"
            return

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = DeepFakeCNN().to(self.device)
        try:
            checkpoint = self._load_checkpoint()
            state_dict = checkpoint.get("model_state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
            self.model.load_state_dict(state_dict)
            self.model.eval()
            self._load_calibration()
            self.model_status = "trained_model_loaded"
        except Exception as e:
            warnings.warn(f"Failed to load deepfake model: {e}")
            self.model_status = "checkpoint_load_failed"

    def _load_checkpoint(self):
        try:
            return torch.load(self.checkpoint_path, map_location=self.device, weights_only=True)
        except TypeError:
            return torch.load(self.checkpoint_path, map_location=self.device)

    @staticmethod
    def _default_checkpoint_path() -> Path:
        return Path(__file__).resolve().parents[2] / "models" / "deepfake_mel_cnn.pt"

    @staticmethod
    def _default_calibration_path() -> Path:
        return Path(__file__).resolve().parents[2] / "models" / "deepfake_calibration.json"

    def _calibration_path_for_checkpoint(self, checkpoint_path: Path) -> Path:
        sidecar = checkpoint_path.with_name(f"{checkpoint_path.stem}_calibration.json")
        if sidecar.exists():
            return sidecar
        return self._default_calibration_path()

    def _load_calibration(self) -> None:
        if not self.calibration_path.exists():
            return
        try:
            with self.calibration_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            self.operating_threshold = float(data.get("operating_threshold", self.operating_threshold))
            self.soft_audio_threshold = float(data.get("soft_audio_threshold", self.soft_audio_threshold))
            self.hard_audio_threshold = float(data.get("hard_audio_threshold", self.hard_audio_threshold))
            self.target_fpr = data.get("target_fpr")
            self.calibration_status = data.get("status", "calibrated")
            self.calibration_note = data.get("note", "Calibrated threshold loaded.")
        except Exception as e:
            warnings.warn(f"Failed to load deepfake calibration: {e}")
            self.calibration_status = "calibration_load_failed"

    def _has_enough_signal(self, y) -> bool:
        if hasattr(self.extractor, "has_speech"):
            return bool(self.extractor.has_speech(y))
        samples = np.asarray(y, dtype=np.float32)
        if samples.size == 0:
            return False
        rms = float(np.sqrt(np.mean(np.square(samples))))
        peak = float(np.max(np.abs(samples)))
        return rms >= 1e-4 and peak >= 1e-3

    def detect(self, audio_path: str) -> Dict:
        """
        Analyze audio for deepfake indicators.
        Returns score (0-1) and confidence.
        """
        if self.model_status != "trained_model_loaded":
            return {
                "deepfake_score": None,
                "confidence": "unavailable",
                "model_status": self.model_status,
                "used_in_fusion": False,
                "model_name": "log_mel_cnn_v1",
                "checkpoint_path": str(self.checkpoint_path),
                "calibration_status": self.calibration_status,
                "operating_threshold": self.operating_threshold,
                "soft_audio_threshold": self.soft_audio_threshold,
                "hard_audio_threshold": self.hard_audio_threshold,
                "audio_signal_strength": "unavailable",
                "note": "Deepfake pipeline implemented, trained model pending."
            }

        if not TORCH_AVAILABLE or not LIBROSA_AVAILABLE or self.model is None:
            return {
                "deepfake_score": None,
                "confidence": "unavailable",
                "model_status": "audio_libraries_unavailable",
                "used_in_fusion": False,
                "note": "Audio ML libraries missing. Install torch and librosa for audio inference."
            }

        try:
            y = self.extractor.load_audio(audio_path)
            activity = (
                self.extractor.audio_activity(y)
                if hasattr(self.extractor, "audio_activity")
                else {"speech_like": self._has_enough_signal(y)}
            )
            if not activity.get("speech_like", False):
                return {
                    "deepfake_score": None,
                    "raw_deepfake_score": None,
                    "fusion_deepfake_score": 0.0,
                    "operating_threshold": round(self.operating_threshold, 4),
                    "soft_audio_threshold": round(self.soft_audio_threshold, 4),
                    "hard_audio_threshold": round(self.hard_audio_threshold, 4),
                    "audio_signal_strength": "no_speech",
                    "calibrated_decision": "unavailable",
                    "confidence": "unavailable",
                    "model_status": self.model_status,
                    "calibration_status": self.calibration_status,
                    "target_fpr": self.target_fpr,
                    "used_in_fusion": False,
                    "model_name": "log_mel_cnn_v1",
                    "activity": activity,
                    "note": "Audio contained too little speech-like signal for deepfake inference."
                }

            if hasattr(self.extractor, "iter_windows"):
                windows = list(self.extractor.iter_windows(y))
            else:
                windows = [self.extractor.preprocess_audio(y)]

            scores = []
            with torch.no_grad():
                for y_proc in windows:
                    log_mel = self.extractor.extract_mel(y_proc)
                    input_tensor = self.extractor.to_tensor(log_mel).to(self.device)
                    scores.append(float(self.model(input_tensor).item()))
            score = max(scores) if scores else 0.0

            if score < self.soft_audio_threshold:
                audio_signal_strength = "ignored"
                calibrated_decision = "not_synthetic"
                fusion_score = 0.0
                used_in_fusion = False
            elif score < self.hard_audio_threshold:
                audio_signal_strength = "weak"
                calibrated_decision = "weak_synthetic_signal"
                fusion_score = score
                used_in_fusion = True
            else:
                audio_signal_strength = "strong"
                calibrated_decision = "synthetic"
                fusion_score = score
                used_in_fusion = True

            nearest_threshold = (
                self.soft_audio_threshold
                if score < self.hard_audio_threshold
                else self.hard_audio_threshold
            )
            distance = abs(score - nearest_threshold)
            confidence = "high" if distance > 0.20 else "medium" if distance > 0.05 else "low"

            return {
                "deepfake_score": round(score, 3),
                "raw_deepfake_score": round(score, 3),
                "fusion_deepfake_score": round(fusion_score, 3),
                "operating_threshold": round(self.operating_threshold, 4),
                "soft_audio_threshold": round(self.soft_audio_threshold, 4),
                "hard_audio_threshold": round(self.hard_audio_threshold, 4),
                "audio_signal_strength": audio_signal_strength,
                "calibrated_decision": calibrated_decision,
                "confidence": confidence,
                "model_status": self.model_status,
                "calibration_status": self.calibration_status,
                "target_fpr": self.target_fpr,
                "used_in_fusion": used_in_fusion,
                "model_name": "log_mel_cnn_v1",
                "activity": activity,
            }
        except Exception as e:
            warnings.warn(f"Deepfake detection failed: {e}")
            return {
                "deepfake_score": None,
                "confidence": "unavailable",
                "model_status": "inference_failed",
                "calibration_status": self.calibration_status,
                "audio_signal_strength": "unavailable",
                "calibrated_decision": "unavailable",
                "fusion_deepfake_score": 0.0,
                "operating_threshold": round(self.operating_threshold, 4),
                "soft_audio_threshold": round(self.soft_audio_threshold, 4),
                "hard_audio_threshold": round(self.hard_audio_threshold, 4),
                "used_in_fusion": False,
                "error": str(e)
            }
