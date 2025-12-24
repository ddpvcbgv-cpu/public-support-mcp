from __future__ import annotations

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
