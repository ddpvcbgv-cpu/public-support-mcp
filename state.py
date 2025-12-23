from __future__ import annotations

from threading import Lock
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, Field


class SessionState(BaseModel):
    user_keywords: List[str] = Field(default_factory=list)
    known_facts: Dict[str, Any] = Field(default_factory=dict)
    missing_info: List[str] = Field(default_factory=list)
    chosen_domain: Optional[str] = None
    shown_cards: List[str] = Field(default_factory=list)
    accepted_cards: List[str] = Field(default_factory=list)
    rejected_cards: List[str] = Field(default_factory=list)
    urgency_level: int = 3
    region_hint: Optional[str] = None
    handoff_intent: Optional[str] = None


class SessionStore:
    """In-memory session store. Thread-safe for demo purposes."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionState] = {}
        self._lock = Lock()

    def get(self, session_id: Optional[str]) -> Tuple[str, SessionState]:
        """Fetch existing session or create a new one."""
        with self._lock:
            if not session_id or session_id not in self._sessions:
                session_id = uuid4().hex
                self._sessions[session_id] = SessionState()
            return session_id, self._sessions[session_id]

    def set(self, session_id: str, state: SessionState) -> None:
        """Persist a modified session."""
        with self._lock:
            self._sessions[session_id] = state


# Global store instance used by FastAPI routes
SESSION_STORE = SessionStore()

