from __future__ import annotations

from threading import Lock
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, Field

from schemas import ConversationTurn, UserProfile


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
    
    # 🆕 Context-Aware 확장
    conversation_history: List[ConversationTurn] = Field(default_factory=list, description="대화 히스토리")
    user_profile: UserProfile = Field(default_factory=UserProfile, description="추론된 사용자 프로파일")
    interaction_count: int = Field(default=0, description="상호작용 횟수")
    
    # v1.2: 이전 응답의 mcp_meta 저장 (confirmation 처리용)
    previous_mcp_meta: Optional[Dict[str, Any]] = Field(default=None, description="이전 응답의 mcp_meta")


class SessionStore:
    """In-memory session store. Thread-safe for demo purposes."""

    def __init__(self) -> None:
        self._sessions: Dict[str, SessionState] = {}
        self._session_timestamps: Dict[str, float] = {}  # v1.2 H: TTL 추적
        self._lock = Lock()

    def get(self, session_id: Optional[str]) -> Tuple[str, SessionState]:
        """Fetch existing session or create a new one."""
        from time import time
        
        with self._lock:
            # v1.2 H: TTL 30분 체크
            now = time()
            expired_sessions = [
                sid for sid, timestamp in self._session_timestamps.items()
                if now - timestamp > 1800  # 30분 = 1800초
            ]
            for sid in expired_sessions:
                self._sessions.pop(sid, None)
                self._session_timestamps.pop(sid, None)
            
            if not session_id or session_id not in self._sessions:
                session_id = uuid4().hex
                self._sessions[session_id] = SessionState()
                self._session_timestamps[session_id] = now
            else:
                # 접근 시간 업데이트
                self._session_timestamps[session_id] = now
            return session_id, self._sessions[session_id]

    def set(self, session_id: str, state: SessionState) -> None:
        """Persist a modified session."""
        from time import time
        
        with self._lock:
            self._sessions[session_id] = state
            self._session_timestamps[session_id] = time()


# Global store instance used by FastAPI routes
SESSION_STORE = SessionStore()

