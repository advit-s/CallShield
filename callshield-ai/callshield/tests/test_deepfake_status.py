"""Deepfake detector status honesty tests."""

from pathlib import Path

from callshield.engine import deepfake as deepfake_module
from callshield.engine.deepfake import DeepFakeDetector


def test_no_checkpoint_returns_no_score_and_not_used_in_fusion(tmp_path):
    missing_checkpoint = tmp_path / "missing_deepfake_mel_cnn.pt"
    detector = DeepFakeDetector(model_path=str(missing_checkpoint))

    result = detector.detect(str(tmp_path / "audio.wav"))

    assert result["deepfake_score"] is None
    assert result["confidence"] == "unavailable"
    assert result["model_status"] == "pipeline_implemented_no_trained_model"
    assert result["used_in_fusion"] is False


def test_trained_checkpoint_status_returns_numeric_score_and_used_in_fusion(tmp_path, monkeypatch):
    checkpoint = tmp_path / "deepfake_mel_cnn.pt"
    checkpoint.write_bytes(b"test checkpoint marker")

    class FakeTensor:
        def to(self, device):
            return self

    class FakeExtractor:
        def load_audio(self, audio_path):
            return [0.0]

        def preprocess_audio(self, y):
            return y

        def extract_mel(self, y):
            return [[0.0]]

        def to_tensor(self, log_mel):
            return FakeTensor()

    class FakeScore:
        def item(self):
            return 0.73

    class FakeModel:
        def __call__(self, input_tensor):
            return FakeScore()

    class FakeNoGrad:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeTorch:
        @staticmethod
        def no_grad():
            return FakeNoGrad()

    monkeypatch.setattr(deepfake_module, "TORCH_AVAILABLE", True)
    monkeypatch.setattr(deepfake_module, "LIBROSA_AVAILABLE", True)
    monkeypatch.setattr(deepfake_module, "torch", FakeTorch(), raising=False)

    detector = object.__new__(DeepFakeDetector)
    detector.extractor = FakeExtractor()
    detector.checkpoint_path = checkpoint
    detector.model = FakeModel()
    detector.model_status = "trained_model_loaded"
    detector.device = "cpu"
    detector.operating_threshold = 0.5
    detector.target_fpr = 0.1
    detector.calibration_status = "calibrated"

    result = detector.detect(str(tmp_path / "audio.wav"))

    assert isinstance(result["deepfake_score"], float)
    assert result["deepfake_score"] == 0.73
    assert result["fusion_deepfake_score"] == 0.73
    assert result["calibrated_decision"] == "synthetic"
    assert result["model_status"] == "trained_model_loaded"
    assert result["used_in_fusion"] is True


def test_trained_checkpoint_below_calibrated_threshold_has_zero_fusion_score(tmp_path, monkeypatch):
    checkpoint = tmp_path / "deepfake_mel_cnn.pt"
    checkpoint.write_bytes(b"test checkpoint marker")

    class FakeTensor:
        def to(self, device):
            return self

    class FakeExtractor:
        def load_audio(self, audio_path):
            return [0.0]

        def preprocess_audio(self, y):
            return y

        def extract_mel(self, y):
            return [[0.0]]

        def to_tensor(self, log_mel):
            return FakeTensor()

    class FakeScore:
        def item(self):
            return 0.73

    class FakeModel:
        def __call__(self, input_tensor):
            return FakeScore()

    class FakeNoGrad:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeTorch:
        @staticmethod
        def no_grad():
            return FakeNoGrad()

    monkeypatch.setattr(deepfake_module, "TORCH_AVAILABLE", True)
    monkeypatch.setattr(deepfake_module, "LIBROSA_AVAILABLE", True)
    monkeypatch.setattr(deepfake_module, "torch", FakeTorch(), raising=False)

    detector = object.__new__(DeepFakeDetector)
    detector.extractor = FakeExtractor()
    detector.checkpoint_path = checkpoint
    detector.model = FakeModel()
    detector.model_status = "trained_model_loaded"
    detector.device = "cpu"
    detector.operating_threshold = 0.9683
    detector.target_fpr = 0.1
    detector.calibration_status = "calibrated"

    result = detector.detect(str(tmp_path / "audio.wav"))

    assert result["deepfake_score"] == 0.73
    assert result["fusion_deepfake_score"] == 0.0
    assert result["calibrated_decision"] == "not_synthetic"
    assert result["used_in_fusion"] is True
