from __future__ import annotations

from typing import Dict, Any, Optional, Literal

from state import SessionState


# v0.50 엔진 철학: "속도와 방향은 사용자가 정한다"
SAFETY_CLOSING_MESSAGES = [
    "지금 이 단계에서\n취업을 오래 못 했다는 사실이\n불리한 자격이 되는 건 아닙니다.\n\n도움을 받을 수 있는지 확인하고,\n어디서부터 다시 시작할지 고르고 계신 지금 이 과정 자체가\n이미 한 걸음입니다.\n\n속도와 방향은\n지금 질문하신 분이 정하셔도 괜찮아요.",
    
    "지금 이 순간,\n무엇을 말해야 할지 몰라서 막막하셨을 수도 있어요.\n\n그래도 지금 이렇게 질문해주신 것만으로\n이미 충분히 의미 있는 과정입니다.\n\n천천히 가셔도 괜찮고,\n중간에 쉬셔도 괜찮습니다.\n\n속도는 질문하신 분이 정하셔도 됩니다.",
    
    "지금 상황이 어렵다는 걸\n말씀해주신 것 자체가\n이미 한 걸음입니다.\n\n비교나 평가 없이,\n지금 상황에서 열려 있는 선택지부터\n차분하게 하나씩 살펴보면 괜찮아요.\n\n부담 없이 진행하셔도 됩니다.",
]


# 상황별 맞춤 감정 안전 메시지
CONTEXTUAL_SAFETY_MESSAGES = {
    "취업_장기공백": "지금 이 단계에서\n취업을 오래 못 했다는 사실이 불리한 자격이 되는 건 아닙니다.\n\n도움을 받을 수 있는지 확인하고, 어디서부터 다시 시작할지 고르고 계신\n지금 이 과정 자체가 이미 한 걸음입니다.\n\n속도와 방향은 지금 질문하신 분이 정하셔도 괜찮아요.",
    
    "소득_없음": "지금 소득이 없다는 게\n부끄러운 일이 아니에요.\n\n오히려 지금 도움을 찾고 계신다는 게\n상황을 정리하려는 과정입니다.\n\n천천히 하나씩 살펴보셔도 괜찮아요.",
    
    "긴급상황": "지금 급하신 상황일 수 있어요.\n\n그래도 지금 질문해주신 것만으로\n이미 방향을 잡기 시작하신 겁니다.\n\n하나씩 차근차근 진행하셔도 괜찮습니다.",
}


def detect_crisis_intent(user_message: str) -> Optional[Dict[str, Any]]:
    """
    v1.2 E 요구사항: Crisis 2-step guardrail
    의도-신호 조합 기반 감지 (단일 키워드 금지)
    """
    message_lower = user_message.lower()
    
    # (self-harm intent + method/time)
    self_harm_intents = ["자살", "죽고 싶", "끝내고 싶", "생각"]
    self_harm_methods = ["약", "칼", "밧줄", "추락", "목매", "가스"]
    self_harm_time = ["지금", "오늘", "당장", "지금 당장", "곧"]
    
    has_self_harm_intent = any(intent in message_lower for intent in self_harm_intents)
    has_method = any(method in message_lower for method in self_harm_methods)
    has_time_urgency = any(time_word in message_lower for time_word in self_harm_time)
    
    if has_self_harm_intent and (has_method or has_time_urgency):
        return {
            "type": "self_harm",
            "severity": "high",
            "crisis_type": "self_harm"
        }
    
    # (violence/threat + perpetrator/place)
    violence_keywords = ["성폭행", "가정폭력", "폭행", "구타", "때림", "협박", "위협"]
    perpetrator_keywords = ["가족", "부모", "배우자", "동거인", "남편", "아내"]
    place_keywords = ["집", "집안", "현재", "지금"]
    
    has_violence = any(v in message_lower for v in violence_keywords)
    has_perpetrator = any(p in message_lower for p in perpetrator_keywords)
    has_place = any(pl in message_lower for pl in place_keywords)
    
    if has_violence and (has_perpetrator or has_place):
        return {
            "type": "violence",
            "severity": "high",
            "crisis_type": "violence_domestic"
        }
    
    # (eviction/starvation + "today/immediately" urgency)
    eviction_keywords = ["퇴거", "쫓겨", "내쫓", "강제퇴거"]
    starvation_keywords = ["굶", "배고", "식사 못", "밥 못"]
    urgency_keywords = ["오늘", "내일", "당장", "지금", "즉시", "급해"]
    
    has_eviction = any(e in message_lower for e in eviction_keywords)
    has_starvation = any(s in message_lower for s in starvation_keywords)
    has_immediate_urgency = any(u in message_lower for u in urgency_keywords)
    
    if (has_eviction or has_starvation) and has_immediate_urgency:
        return {
            "type": "eviction_starvation",
            "severity": "high",
            "crisis_type": "unclear_high_risk"
        }
    
    return None


def generate_crisis_step1_question(crisis_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    v1.2 E: Step 1 - 안전 확인 질문
    """
    crisis_type = crisis_info.get("crisis_type")
    
    if crisis_type == "self_harm":
        return {
            "question": "지금 안전한가요?",
            "options": ["안전함", "위험함", "확실하지 않음"],
            "expected_values": ["SAFE", "UNSAFE", "NOT_SURE"]
        }
    elif crisis_type == "violence_domestic":
        return {
            "question": "지금 안전한가요?",
            "options": ["안전함", "위험함", "확실하지 않음"],
            "expected_values": ["SAFE", "UNSAFE", "NOT_SURE"]
        }
    else:  # unclear_high_risk
        return {
            "question": "지금 안전한가요?",
            "options": ["안전함", "위험함", "확실하지 않음"],
            "expected_values": ["SAFE", "UNSAFE", "NOT_SURE"]
        }


def generate_crisis_step2_message(crisis_info: Dict[str, Any], safety_status: Literal["UNSAFE"]) -> str:
    """
    v1.2 E: Step 2 - UNSAFE 확인 시 plain text 메시지
    """
    crisis_type = crisis_info.get("crisis_type")
    
    first_line = "지금은 추가 정보 입력보다 안전이 가장 중요합니다.\n\n"
    
    if crisis_type == "violence_domestic":
        return first_line + "112 (경찰)\n1366 (가정폭력상담소)"
    elif crisis_type == "self_harm":
        return first_line + "119 (소방)\n1393 (자살예방상담)"
    else:  # unclear_high_risk
        return first_line + "112 또는 119\n가까운 응급실/주변 도움 요청"


def compose_safe_response(state: SessionState | None = None) -> str:
    """
    감정 안전을 위한 마무리 문장을 반환한다.
    v0.50: 상황에 맞는 메시지 선택
    """
    import random
    
    # 상황별 맞춤 메시지
    if state:
        keywords = set(state.user_keywords)
        
        if any(kw in keywords for kw in ["취업", "구직", "실직"]):
            if state.interaction_count >= 3:  # 대화가 길어진 경우
                return CONTEXTUAL_SAFETY_MESSAGES["취업_장기공백"]
        
        if any(kw in keywords for kw in ["소득", "생활비", "생계"]):
            if not any(kw in keywords for kw in ["알바", "일", "직장"]):
                return CONTEXTUAL_SAFETY_MESSAGES["소득_없음"]
        
        if state.urgency_level == 1:
            return CONTEXTUAL_SAFETY_MESSAGES["긴급상황"]
    
    # 기본 메시지
    return random.choice(SAFETY_CLOSING_MESSAGES)
