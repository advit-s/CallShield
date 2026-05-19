import whisper
import warnings
from typing import Optional
import torch
from pathlib import Path


class ASRTranscriber:
    """Whisper-based ASR with scam-relevant language support."""

    def __init__(self, model_name: str = "base", device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            self.model = whisper.load_model(self.model_name)
            print(f"Loaded Whisper model: {self.model_name}")
        except Exception as e:
            warnings.warn(f"Could not load Whisper: {e}. Transcription will be limited.")
            self.model = None

    def transcribe(self, audio_path: str or torch.Tensor, language: Optional[str] = None) -> dict:
        """Transcribe audio file or tensor. Returns dict with text, language, segments."""
        if self.model is None:
            return {"text": "", "language": None, "segments": []}

        try:
            if isinstance(audio_path, str):
                result = self.model.transcribe(
                    audio_path,
                    language=language,
                    fp16=False,
                    verbose=False
                )
            else:
                # If tensor, need to save temporarily
                import tempfile
                import soundfile as sf
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    audio_np = audio_path.numpy() if isinstance(audio_path, torch.Tensor) else audio_path
                    if audio_np.ndim > 1:
                        audio_np = audio_np.squeeze()
                    sf.write(f.name, audio_np, 16000)
                    result = self.model.transcribe(f.name, language=language, fp16=False, verbose=False)

            return {
                "text": result.get("text", "").strip(),
                "language": result.get("language"),
                "segments": result.get("segments", []),
                "confidence": result.get("confidence", 0.0)
            }
        except Exception as e:
            warnings.warn(f"Transcription failed: {e}")
            return {"text": "", "language": None, "segments": []}
