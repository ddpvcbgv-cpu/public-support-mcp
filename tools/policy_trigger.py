"""
제도명 공개 트리거 감지 도구
"""
from __future__ import annotations

from typing import Dict, List

from state import SessionState
from constants import POLICY_TRIGGER_KEYWORDS, REQUIRED_PHRASES


def check_policy_trigger(message: str, state: SessionState) -> Dict[str, object]:
    """
    사용자 메시지에서 제도명 공개 트리거를 감지합니다.
    
    트리거 조건:
    - Trigger A: 사용자가 카드 선택 ("이거", "1번", "더 알려줘")
    - Trigger B: 제도명 직접 질문 ("정확히 이름이 뭐예요?")
    - Trigger C: 외부 행동 의도 ("어디로 전화해요?", "신청하려면?")
    
    Args:
        message: 사용자 입력 메시지
        state: 세션 상태
    
    Returns:
        트리거 감지 결과 및 공개할 제도명 정보
    """
    message_lower = message.lower()
    
    triggered = False
    trigger_type = None
    
    # Trigger A: 카드 선택
    if any(keyword in message_lower for keyword in POLICY_TRIGGER_KEYWORDS["card_selection"]):
        triggered = True
        trigger_type = "card_selection"
        # handoff_intent 업데이트
        if not state.handoff_intent:
            state.handoff_intent = "card_selected"
    
    # Trigger B: 제도명 질문
    elif any(keyword in message_lower for keyword in POLICY_TRIGGER_KEYWORDS["policy_name_question"]):
        triggered = True
        trigger_type = "policy_name_question"
    
    # Trigger C: 행동 의도
    elif any(keyword in message_lower for keyword in POLICY_TRIGGER_KEYWORDS["action_intent"]):
        triggered = True
        trigger_type = "action_intent"
        state.handoff_intent = "external_action"
    
    result = {
        "triggered": triggered,
        "trigger_type": trigger_type,
        "warning_message": REQUIRED_PHRASES["policy_warning"] if triggered else None,
    }
    
    # 트리거되었고, 선택된 카드가 있는 경우 제도명 정보 제공
    if triggered and state.accepted_cards:
        # 마지막 선택된 카드에 대한 제도명 제공
        # (실제로는 CARD_LIBRARY에서 매핑된 제도명을 가져와야 함)
        last_card = state.accepted_cards[-1]
        result["policy_info"] = {
            "card_name": last_card,
            "policy_name": _get_policy_name_for_card(last_card),
        }
    
    return result


def _get_policy_name_for_card(card_name: str) -> str:
    """
    카드명에 매핑된 실제 제도명을 반환합니다.
    
    (실제 운영 시에는 tools/cards.py의 CARD_LIBRARY와 연동해야 함)
    """
    # 간단한 매핑 (실제로는 DB나 cards.py에서 가져와야 함)
    policy_mapping = {
        "주거 안심 상담": "주거급여, 긴급복지지원(주거 부문)",
        "체납 완화 점검": "에너지바우처, 긴급복지지원",
        "안전 이사 대비": "긴급주거지원, LH 임시거처 제공",
        "생활비 숨통 점검": "생계급여, 긴급복지지원(생계 부문)",
        "식비·생필품 완충": "푸드뱅크, 지역 무료급식소",
        "연체 리듬 조정": "긴급복지지원, 신용회복지원",
        "진료비 부담 점검": "의료급여, 긴급의료비 지원",
        "돌봄 공백 메우기": "노인장기요양보험, 장애인활동지원",
        "장애·건강 연계 확인": "장애인연금, 장애수당",
        "소득 회복 탐색": "취업성공패키지, 국민취업지원제도",
        "경험 전환 지원": "내일배움카드, 국비지원 교육",
        "단기 수입 연결": "지역일자리, 공공근로",
    }
    
    return policy_mapping.get(card_name, "관련 제도")


def reveal_policy_name_if_triggered(
    message: str,
    state: SessionState
) -> Dict[str, object]:
    """
    제도명 공개 트리거를 확인하고, 조건 충족 시 제도명을 공개합니다.
    
    (이 함수는 check_policy_trigger의 래퍼입니다)
    """
    return check_policy_trigger(message, state)

