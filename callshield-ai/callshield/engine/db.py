"""CallShield SQLite Persistence Layer.

Thread-safe database integration with WAL mode for FastAPI uvicorn concurrency.
"""

import os
import json
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

# Thread lock for SQLite write serialization
_DB_LOCK = threading.Lock()


def get_db_path() -> Path:
    """Resolve the SQLite database path, defaulting to callshield.db in project root."""
    default_path = Path(__file__).resolve().parents[2] / "callshield.db"
    env_path = os.environ.get("CALLSHIELD_DATABASE_PATH")
    if env_path:
        return Path(env_path)
    return default_path


class CallShieldDatabase:
    """Product-grade SQLite manager for CallShield data persistence."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_db_path()
        self._initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection and set thread-concurrency options."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrency (concurrent reads and writes)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _initialize_db(self) -> None:
        """Ensure all required tables are created in SQLite."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with _DB_LOCK:
            conn = self._get_connection()
            try:
                with conn:
                    # 1. Calls table
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS calls (
                            call_id TEXT PRIMARY KEY,
                            user_id TEXT,
                            result_json TEXT,
                            transcript TEXT,
                            timestamp TEXT
                        )
                    """)
                    # 2. Feedback table
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS feedback (
                            call_id TEXT PRIMARY KEY,
                            is_scam INTEGER,
                            feedback_notes TEXT,
                            reported_cues_json TEXT,
                            timestamp TEXT,
                            FOREIGN KEY (call_id) REFERENCES calls (call_id) ON DELETE CASCADE
                        )
                    """)
                    # 3. Consented speakers table
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS speakers (
                            speaker_id TEXT PRIMARY KEY,
                            name TEXT,
                            consent_given INTEGER,
                            voice_embedding_json TEXT,
                            timestamp TEXT
                        )
                    """)
            finally:
                conn.close()

    def store_call(self, call_id: str, user_id: Optional[str], result: Dict[str, Any],
                   transcript: Optional[str] = None) -> None:
        """Store or update a call result record."""
        with _DB_LOCK:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO calls (call_id, user_id, result_json, transcript, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(call_id) DO UPDATE SET
                            user_id = excluded.user_id,
                            result_json = excluded.result_json,
                            transcript = COALESCE(excluded.transcript, calls.transcript),
                            timestamp = excluded.timestamp
                        """,
                        (
                            call_id,
                            user_id,
                            json.dumps(result),
                            transcript,
                            result.get("timestamp", datetime.now().isoformat())
                        )
                    )
            finally:
                conn.close()

    def get_call(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific call summary result."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT call_id, user_id, result_json, transcript, timestamp FROM calls WHERE call_id = ?",
                (call_id,)
            ).fetchone()
            if not row:
                return None
            
            result = json.loads(row["result_json"])
            return {
                "call_id": row["call_id"],
                "user_id": row["user_id"],
                "result": result,
                "transcript": row["transcript"],
                "timestamp": row["timestamp"]
            }
        finally:
            conn.close()

    def store_feedback(self, call_id: str, is_scam: bool, notes: Optional[str],
                       reported_cues: List[str]) -> None:
        """Store user feedback for a specific call ID."""
        with _DB_LOCK:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO feedback (call_id, is_scam, feedback_notes, reported_cues_json, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(call_id) DO UPDATE SET
                            is_scam = excluded.is_scam,
                            feedback_notes = excluded.feedback_notes,
                            reported_cues_json = excluded.reported_cues_json,
                            timestamp = excluded.timestamp
                        """,
                        (
                            call_id,
                            1 if is_scam else 0,
                            notes,
                            json.dumps(reported_cues),
                            datetime.now().isoformat()
                        )
                    )
            finally:
                conn.close()

    def get_feedback(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve feedback associated with a call ID."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT call_id, is_scam, feedback_notes, reported_cues_json, timestamp FROM feedback WHERE call_id = ?",
                (call_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "call_id": row["call_id"],
                "is_scam": bool(row["is_scam"]),
                "feedback_notes": row["feedback_notes"],
                "reported_cues": json.loads(row["reported_cues_json"]),
                "timestamp": row["timestamp"]
            }
        finally:
            conn.close()

    def store_speaker(self, speaker_id: str, name: str, consent_given: bool,
                      voice_embedding: Optional[List[float]] = None) -> None:
        """Store consented speaker verification profile."""
        with _DB_LOCK:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute(
                        """
                        INSERT INTO speakers (speaker_id, name, consent_given, voice_embedding_json, timestamp)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(speaker_id) DO UPDATE SET
                            name = excluded.name,
                            consent_given = excluded.consent_given,
                            voice_embedding_json = COALESCE(excluded.voice_embedding_json, speakers.voice_embedding_json),
                            timestamp = excluded.timestamp
                        """,
                        (
                            speaker_id,
                            name,
                            1 if consent_given else 0,
                            json.dumps(voice_embedding) if voice_embedding else None,
                            datetime.now().isoformat()
                        )
                    )
            finally:
                conn.close()

    def get_speaker(self, speaker_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve consented speaker profile."""
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT speaker_id, name, consent_given, voice_embedding_json, timestamp FROM speakers WHERE speaker_id = ?",
                (speaker_id,)
            ).fetchone()
            if not row:
                return None
            return {
                "speaker_id": row["speaker_id"],
                "name": row["name"],
                "consent_given": bool(row["consent_given"]),
                "voice_embedding": json.loads(row["voice_embedding_json"]) if row["voice_embedding_json"] else None,
                "timestamp": row["timestamp"]
            }
        finally:
            conn.close()

    def delete_call(self, call_id: str) -> bool:
        """Delete a call and its corresponding feedback (cascading)."""
        with _DB_LOCK:
            conn = self._get_connection()
            try:
                with conn:
                    # Enforce foreign key constraints
                    conn.execute("PRAGMA foreign_keys = ON;")
                    cursor = conn.execute("DELETE FROM calls WHERE call_id = ?", (call_id,))
                    return cursor.rowcount > 0
            finally:
                conn.close()

    def delete_user_data(self, user_id: str) -> int:
        """Delete all calls and feedback matching user_id. Returns delete count."""
        with _DB_LOCK:
            conn = self._get_connection()
            try:
                with conn:
                    conn.execute("PRAGMA foreign_keys = ON;")
                    # 1. Fetch matching calls first for reporting delete count
                    call_rows = conn.execute("SELECT call_id FROM calls WHERE user_id = ?", (user_id,)).fetchall()
                    call_ids = [row["call_id"] for row in call_rows]
                    
                    if not call_ids:
                        return 0
                    
                    # 2. Deletions cascade to feedback table
                    cursor = conn.execute("DELETE FROM calls WHERE user_id = ?", (user_id,))
                    return cursor.rowcount
            finally:
                conn.close()
