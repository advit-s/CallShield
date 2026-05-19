import torch
import numpy as np
from typing import Optional
import warnings


class SpeakerVerifier:
    """Speaker verification using ECAPA-TDNN embeddings via SpeechBrain."""

    def __init__(self, model_name: str = "speechbrain/ecapa-voxceleb", device: str = "cpu"):
        self.device = torch.device(device)
        self.model_name = model_name
        self.encoder = None
        self.enrolled_embeddings = {}

        try:
            from speechbrain.inference import EncoderClassifier, SpeakerRecognition
            self.encoder = EncoderClassifier.from_hparams(
                source=model_name, run_opts={"device": device}
            )
            print(f"Loaded speaker model from {model_name}")
        except Exception as e:
            warnings.warn(f"Could not load speaker model: {e}. Using random embeddings fallback.")
            self.encoder = None

    def get_embedding(self, audio: torch.Tensor) -> np.ndarray:
        """Get speaker embedding for audio."""
        if self.encoder is not None:
            try:
                with torch.no_grad():
                    embeddings = self.encoder.encode_batch(audio.to(self.device))
                    return embeddings.cpu().numpy().flatten()
            except Exception as e:
                warnings.warn(f"Embedding extraction failed: {e}, using fallback.")
        # Fallback: use simple stats as pseudo-embedding
        return self._fallback_embedding(audio)

    def _fallback_embedding(self, audio: torch.Tensor) -> np.ndarray:
        """Simple feature-based fallback."""
        audio_np = audio.numpy() if isinstance(audio, torch.Tensor) else audio
        if audio_np.ndim > 1:
            audio_np = audio_np.squeeze()

        # Extract simple features
        features = [
            np.mean(audio_np),
            np.std(audio_np),
            np.max(audio_np),
            np.min(audio_np),
            np.sum(audio_np ** 2),  # energy
            np.sum(np.abs(np.diff(audio_np))),  # zero-crossing rate
        ]

        # Expand to 128-dim with frequency domain info
        fft = np.abs(np.fft.rfft(audio_np))[:64]
        if len(fft) < 64:
            fft = np.pad(fft, (0, 64 - len(fft)))

        combined = np.concatenate([np.array(features), fft])
        # Normalize
        if np.linalg.norm(combined) > 0:
            combined = combined / np.linalg.norm(combined)
        return combined

    def enroll_speaker(self, speaker_id: str, audio: torch.Tensor) -> bool:
        """Enroll a speaker's voice for future verification."""
        embedding = self.get_embedding(audio)
        self.enrolled_embeddings[speaker_id] = embedding
        return True

    def verify(self, speaker_id: str, audio: torch.Tensor) -> float:
        """Compare incoming audio against enrolled speaker. Returns cosine similarity."""
        if speaker_id not in self.enrolled_embeddings:
            return 0.5  # Unknown speaker, neutral

        new_embedding = self.get_embedding(audio)
        enrolled = self.enrolled_embeddings[speaker_id]

        # Cosine similarity
        dot = np.dot(new_embedding, enrolled)
        norm = np.linalg.norm(new_embedding) * np.linalg.norm(enrolled)
        if norm == 0:
            return 0.0
        return (dot / norm + 1) / 2  # Normalize to [0, 1]

    def get_identity_mismatch(self, speaker_id: Optional[str], audio: torch.Tensor) -> float:
        """Return identity mismatch score (1 - speaker similarity)."""
        if not speaker_id:
            return 0.0  # No enrollment, can't mismatch
        similarity = self.verify(speaker_id, audio)
        return 1.0 - similarity
