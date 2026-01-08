from __future__ import annotations

from enum import Enum
from threading import Lock
from typing import Any, Dict, List, Literal, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, Field

from schemas import ConversationTurn, UserProfile


class ConversationPhase(str, Enum):
    """대화 단계를 나타내는 Enum"""
    PRE_DECISION = "PRE_DECISION"
    DIRECTION_SELECTED = "DIRECTION_SELECTED"
    EXECUTION_READY = "EXECUTION_READY"


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
    
    # 🆕 v2: 대화 단계 제어
    phase: ConversationPhase = Field(default=ConversationPhase.PRE_DECISION, description="현재 대화 단계")
    
    # 🆕 v3f: Signal Detection Layer
    signal_level: Literal["LEVEL_1", "LEVEL_2", "LEVEL_3"] = Field(
        default="LEVEL_1",
        description="위험/취약 시그널 레벨"
    )
    forced_domain: Optional[str] = Field(
        default=None,
        description="LEVEL_3에서 강제로 고정된 도메인"
    )
    primary_domain: Optional[str] = Field(
        default=None,
        description="LEVEL_2에서 우선 도메인"
    )
    
    # 🆕 분야 선택 매칭용: 이전 턴에 보여준 분야 목록
    last_shown_domains: List[str] = Field(
        default_factory=list,
        description="이전 턴에 보여준 분야 목록 (1번/2번 매칭용)"
    )
    
    # 🆕 안전 리스크 감지: 마지막으로 감지된 안전 리스크 정보
    last_safety_risk: Optional[Dict[str, Any]] = Field(
        default=None,
        description="마지막으로 감지된 안전 리스크 정보 (level, type, raw_match)"
    )


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

