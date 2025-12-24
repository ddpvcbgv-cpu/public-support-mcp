"""의도 분류 엔진 - 사용자 메시지에서 의도를 추출"""
from __future__ import annotations

from typing import Dict, List, Optional

from schemas import ConversationTurn
from state import SessionState


# 의도별 키워드 매핑
INTENT_KEYWORDS: Dict[str, List[str]] = {
    "housing_urgent": ["쫓겨", "퇴거", "집 나가", "당장", "급해"],
    "housing_concern": ["월세", "전세", "보증금", "집", "이사"],
    "living_urgent": ["굶", "밥", "먹을", "당장", "급해", "끊", "전기", "수도"],
    "living_concern": ["생활비", "생계", "공과금", "연체", "관리비", "식비"],
    "medical_urgent": ["아파", "통증", "응급", "수술", "당장"],
    "medical_concern": ["병원", "의료", "건강", "진료", "약값", "치료"],
    "employment_urgent": ["실직", "해고", "잘렸", "소득 없"],
    "employment_concern": ["취업", "구직", "일자리", "교육", "훈련"],
    "emotional_crisis": ["죽고", "살고", "우울", "불안", "힘들", "포기"],
    "emotional_concern": ["상담", "스트레스", "걱정"],
    "info_request": ["알려", "문의", "궁금", "어디", "어떻게"],
    "gratitude": ["감사", "고마워", "도움"],
}


def classify_intent(message: str, state: SessionState) -> str:
    """메시지에서 의도를 분류"""
    message_lower = message.lower()
    
    # 긴급 의도 우선 체크
    for intent in ["housing_urgent", "living_urgent", "medical_urgent", "employment_urgent", "emotional_crisis"]:
        keywords = INTENT_KEYWORDS.get(intent, [])
        if any(kw in message_lower for kw in keywords):
            return intent
    
    # 일반 의도 체크
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in message_lower for kw in keywords):
            return intent
    
    # 대화 히스토리 기반 추론
    if state.conversation_history:
        last_intent = state.conversation_history[-1].intent
        if last_intent and "concern" in last_intent:
            return "follow_up"
    
    return "general"


def extract_keywords_from_message(message: str) -> List[str]:
    """메시지에서 키워드 추출"""
    from tools.normalize import THEME_KEYWORDS
    
    extracted = []
    for keywords in THEME_KEYWORDS.values():
        for word in keywords:
            if word and word in message:
                extracted.append(word)
    
    return list(set(extracted))


def update_conversation_history(
    message: str,
    state: SessionState,
    intent: Optional[str] = None,
    keywords: Optional[List[str]] = None,
) -> None:
    """대화 히스토리 업데이트"""
    from datetime import datetime
    
    if intent is None:
        intent = classify_intent(message, state)
    
    if keywords is None:
        keywords = extract_keywords_from_message(message)
    
    turn = ConversationTurn(
        message=message,
        intent=intent,
        keywords=keywords,
        urgency=state.urgency_level,
        timestamp=datetime.now().isoformat(),
    )
    
    state.conversation_history.append(turn)
    state.interaction_count += 1
    
    # 최근 10개만 유지 (메모리 관리)
    if len(state.conversation_history) > 10:
        state.conversation_history = state.conversation_history[-10:]


def get_primary_intent(state: SessionState) -> Optional[str]:
    """대화 히스토리에서 주요 의도 추출"""
    if not state.conversation_history:
        return None
    
    # 최근 3개 턴에서 가장 많이 나온 의도
    recent_intents = [turn.intent for turn in state.conversation_history[-3:] if turn.intent]
    
    if not recent_intents:
        return None
    
    # 빈도수 계산
    intent_counts = {}
    for intent in recent_intents:
        intent_counts[intent] = intent_counts.get(intent, 0) + 1
    
    # 가장 많이 나온 의도 반환
    return max(intent_counts, key=intent_counts.get)


def get_accumulated_keywords(state: SessionState, limit: int = 10) -> List[str]:
    """대화 히스토리에서 누적된 키워드 추출"""
    all_keywords = []
    for turn in state.conversation_history:
        all_keywords.extend(turn.keywords)
    
    # 중복 제거 + 빈도순 정렬
    from collections import Counter
    keyword_counts = Counter(all_keywords)
    return [kw for kw, _ in keyword_counts.most_common(limit)]

