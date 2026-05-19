"""CallShield Deepfake Detection Engine (v2.3).

CNN-based architecture for synthetic speech detection.
Uses log-mel spectrograms as input.
"""

import os
import warnings
from typing import Dict, Optional
from .audio_features import AudioFeatureExtractor, AUDIO_LIBS_AVAILABLE

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

        self.dropout = nn.Dropout(0.3)
        
        # Based on 16k SR, 4s duration, 256 hop -> ~251 frames
        # After 3 pools (2x2): 128x251 -> 64x125 -> 32x62 -> 16x31
        self.fc1 = nn.Linear(128 * 16 * 31, 256)
        self.fc2 = nn.Linear(256, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        if not TORCH_AVAILABLE:
            return x
        x = self.pool1(F.relu(self.bn1(self.conv1(x))))
        x = self.pool2(F.relu(self.bn2(self.conv2(x))))
        x = self.pool3(F.relu(self.bn3(self.conv3(x))))
        
        x = torch.flatten(x, 1)
        x = self.dropout(F.relu(self.fc1(x)))
        x = self.fc2(x)
        return self.sigmoid(x)


class DeepFakeDetector:
    """Inference engine for deepfake detection."""

    def __init__(self, model_path: Optional[str] = None):
        self.extractor = AudioFeatureExtractor()
        
        if TORCH_AVAILABLE:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = DeepFakeCNN().to(self.device)
            self.model_status = "uninitialized"
            
            if model_path and os.path.exists(model_path):
                try:
                    self.model.load_state_dict(torch.load(model_path, map_location=self.device))
                    self.model.eval()
                    self.model_status = "loaded"
                except Exception as e:
                    warnings.warn(f"Failed to load deepfake model: {e}")
            else:
                self.model.eval()
                self.model_status = "placeholder"
        else:
            self.model = None
            self.model_status = "unavailable"
            self.device = "cpu"

    def detect(self, audio_path: str) -> Dict:
        """
        Analyze audio for deepfake indicators.
        Returns score (0-1) and confidence.
        """
        if not TORCH_AVAILABLE or not AUDIO_LIBS_AVAILABLE:
            return {
                "deepfake_score": 0.05,  # Baseline safe score
                "confidence": "none",
                "model_status": "unavailable",
                "note": "Audio ML libraries (torch/librosa) missing."
            }

        try:
            y = self.extractor.load_audio(audio_path)
            y_proc = self.extractor.preprocess_audio(y)
            log_mel = self.extractor.extract_mel(y_proc)
            input_tensor = self.extractor.to_tensor(log_mel).to(self.device)
            
            with torch.no_grad():
                score = self.model(input_tensor).item()
            
            # Simple confidence heuristic based on score extremity
            confidence = "high" if abs(score - 0.5) > 0.35 else "medium"
            if self.model_status == "placeholder":
                score = 0.05 
                confidence = "low"

            return {
                "deepfake_score": round(score, 3),
                "confidence": confidence,
                "model_status": self.model_status,
                "model_name": "log_mel_cnn_v1"
            }
        except Exception as e:
            warnings.warn(f"Deepfake detection failed: {e}")
            return {
                "deepfake_score": 0.0,
                "confidence": "none",
                "error": str(e)
            }
