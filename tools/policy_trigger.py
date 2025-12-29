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
    - Trigger A: 사용자가 카드 선택 ("이거", "1번", "더 알려줘", "문화누리카드 더 알려주세요")
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
    matched_card = None
    
    # 먼저 메시지에 카드명이 직접 언급되었는지 확인
    available_cards = state.shown_cards or state.accepted_cards or []
    for card in available_cards:
        # 카드명의 핵심 키워드 추출 (예: "문화누리카드 신청" -> "문화누리카드")
        card_keywords = card.replace(" 신청", "").replace(" 연결", "").replace(" 점검", "").replace(" 대비", "")
        if card_keywords.lower() in message_lower or any(word in message_lower for word in card_keywords.split() if len(word) > 2):
            matched_card = card
            triggered = True
            trigger_type = "card_selection"
            break
    
    # Trigger A: 카드 선택 키워드
    if not triggered and any(keyword in message_lower for keyword in POLICY_TRIGGER_KEYWORDS["card_selection"]):
        triggered = True
        trigger_type = "card_selection"
        # handoff_intent 업데이트
        if not state.handoff_intent:
            state.handoff_intent = "card_selected"
    
    # Trigger B: 제도명 질문
    if not triggered and any(keyword in message_lower for keyword in POLICY_TRIGGER_KEYWORDS["policy_name_question"]):
        triggered = True
        trigger_type = "policy_name_question"
    
    # Trigger C: 행동 의도
    if not triggered and any(keyword in message_lower for keyword in POLICY_TRIGGER_KEYWORDS["action_intent"]):
        triggered = True
        trigger_type = "action_intent"
        state.handoff_intent = "external_action"
    
    result = {
        "triggered": triggered,
        "trigger_type": trigger_type,
        "warning_message": REQUIRED_PHRASES["policy_warning"] if triggered else None,
    }
    
    # 트리거되었고, 카드 정보가 있는 경우 제도명 정보 제공
    if triggered:
        # 매칭된 카드가 있으면 사용, 없으면 shown_cards나 accepted_cards의 마지막 항목 사용
        target_card = matched_card
        if not target_card:
            if state.shown_cards:
                target_card = state.shown_cards[-1]
            elif state.accepted_cards:
                target_card = state.accepted_cards[-1]
        
        if target_card:
            result["policy_info"] = {
                "card_name": target_card,
                "policy_name": _get_policy_name_for_card(target_card),
            }
            result["message"] = REQUIRED_PHRASES["policy_reveal"].format(policy_name=_get_policy_name_for_card(target_card))
    
    return result


def _get_policy_name_for_card(card_name: str) -> str:
    """
    카드명에 매핑된 실제 제도명을 반환합니다.
    
    (실제 운영 시에는 tools/cards.py의 CARD_LIBRARY와 연동해야 함)
    """
    # 간단한 매핑 (실제로는 DB나 cards.py에서 가져와야 함)
    policy_mapping = {
        # 주거·월세
        "주거 안심 상담": "주거급여, 긴급복지지원(주거 부문)",
        "체납 완화 점검": "에너지바우처, 긴급복지지원",
        "안전 이사 대비": "긴급주거지원, LH 임시거처 제공",
        # 생활 유지
        "생활비 숨통 점검": "생계급여, 긴급복지지원(생계 부문)",
        "식비·생필품 완충": "푸드뱅크, 지역 무료급식소",
        "연체 리듬 조정": "긴급복지지원, 신용회복지원",
        # 의료·돌봄
        "진료비 부담 점검": "의료급여, 긴급의료비 지원",
        "돌봄 공백 메우기": "노인장기요양보험, 장애인활동지원",
        "장애·건강 연계 확인": "장애인연금, 장애수당",
        # 고용·교육
        "소득 회복 탐색": "취업성공패키지, 국민취업지원제도",
        "경험 전환 지원": "내일배움카드, 국비지원 교육",
        "단기 수입 연결": "지역일자리, 공공근로",
        # 문화·여가
        "문화누리카드 신청": "문화누리카드 (기초생활수급자·차상위계층 대상)",
        "청년문화패스": "청년문화패스 (만 19~34세 청년 대상)",
        "지역 공연·전시 할인": "지역 문화시설 무료/할인 프로그램",
        # 평생교육
        "평생학습관 무료 강좌": "지역 평생학습관 무료/저렴 강좌",
        "직업 전환 교육 (국비지원)": "내일배움카드, 국비지원 직업훈련",
        "온라인 무료 강의 (K-MOOC)": "K-MOOC (한국형 온라인 공개강좌)",
        # 참여·활동
        "지역 자원봉사 연결": "1365 자원봉사포털",
        "커뮤니티·동아리 참여": "지역 주민센터·복지관 동아리 프로그램",
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

