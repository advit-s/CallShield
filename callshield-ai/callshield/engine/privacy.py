"""CallShield Privacy & Security Utilities.

B2B-grade privacy: no raw audio stored, phone numbers hashed,
speaker enrollment requires consent, explainable warnings.
"""

import hashlib
import hmac
import secrets
import tempfile
import os
from typing import Optional
from pathlib import Path


class PrivacyLayer:
    """Privacy-first utilities for CallShield."""

    @staticmethod
    def hash_phone(phone: str) -> str:
        """Hash a phone number using HMAC-SHA256 with an environment pepper.
        Returns a secure, one-way hash."""
        # Normalize: remove non-digits
        normalized = ''.join(c for c in phone if c.isdigit())
        pepper = os.environ.get("CALLSHIELD_PHONE_PEPPER", "callshield_dev_phone_pepper_change_me")
        if os.environ.get("CALLSHIELD_ENV", "development").lower() == "production" and pepper == "callshield_dev_phone_pepper_change_me":
            raise RuntimeError("PRODUCTION SECURITY VIOLATION: Default CALLSHIELD_PHONE_PEPPER pepper cannot be used in production.")
        return hmac.new(pepper.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def generate_call_id() -> str:
        """Generate a unique call ID."""
        return secrets.token_hex(16)

    @staticmethod
    def hash_audio_path(path: str) -> str:
        """Hash an audio file path for safe storage."""
        return hashlib.sha256(path.encode()).hexdigest()[:16]

    @staticmethod
    def get_temp_dir() -> str:
        """Get a secure temporary directory."""
        return tempfile.mkdtemp(prefix="callshield_")


class AudioSanitizer:
    """Handle audio data securely: no raw storage."""

    def __init__(self):
        self._tempdir = PrivacyLayer.get_temp_dir()

    def sanitize_and_save(self, audio_data: bytes,
                          call_id: Optional[str] = None) -> tuple:
        """Save audio to a temp file, return path and metadata hash."""
        if not call_id:
            call_id = PrivacyLayer.generate_call_id()
        temp_path = os.path.join(self._tempdir, f"{call_id}.wav")
        with open(temp_path, "wb") as f:
            f.write(audio_data)
        return temp_path, call_id

    def cleanup(self, path: Optional[str] = None):
        """Remove temporary audio files."""
        if path and os.path.exists(path):
            os.remove(path)

    def __del__(self):
        """Ensure cleanup on deletion."""
        for f in os.listdir(self._tempdir):
            try:
                os.remove(os.path.join(self._tempdir, f))
            except Exception:
                pass
        try:
            os.rmdir(self._tempdir)
        except Exception:
            pass
