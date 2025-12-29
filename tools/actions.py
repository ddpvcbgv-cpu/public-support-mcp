from __future__ import annotations

from typing import Dict

from state import SessionState


def generate_action_steps(state: SessionState) -> Dict[str, str]:
    """지금 바로 할 수 있는 1~3단계 행동을 제안한다."""
    from tools.domains import DOMAIN_HINTS, DOMAIN_PRIORITY
    from tools.cards import CARD_LIBRARY
    
    # 가장 최근에 본 카드가 있으면 그것을 기준으로 행동 단계 제공
    target_card = None
    if state.shown_cards:
        # 가장 최근에 본 카드 찾기
        for card_name in reversed(state.shown_cards):
            for domain_cards in CARD_LIBRARY.values():
                for card in domain_cards:
                    if card["card"] == card_name:
                        target_card = card
                        break
                if target_card:
                    break
            if target_card:
                break
    
    # 카드 정보가 있으면 그것을 활용, 없으면 도메인 기반으로 생성
    if target_card:
        # 카드의 "지금_하실_수_있는_말"을 활용
        say_phrase = target_card.get("지금_하실_수_있는_말", "")
        where_info = target_card.get("where", "")
        how_info = target_card.get("how", "")
        stuck_info = target_card.get("막히면", "")
        
        today = (
            f"오늘은 짧게 상황을 한 문장으로 정리해두세요. "
            f"예) \"{say_phrase}\" 같은 문장을 준비하시면 상담 시 부담이 줄어요."
        )
        
        tomorrow = (
            f"내일은 {where_info}에 문의하시거나, "
            f"{how_info.split('.')[0] if how_info else '지원 가능성만 먼저 확인하고 싶다'}고 말씀하시면 됩니다."
        )
        
        stuck = stuck_info or (
            "연결이 어렵거나 답을 못 들으면, '신청'이 아니라 '자격 확인 상담'만 먼저 부탁한다고 말해보세요. "
            "서류가 없어도 현재 상황만 말하고 가볍게 시작하셔도 됩니다."
        )
    else:
        # 도메인 기반 기본 행동 단계
        domain = state.chosen_domain
        if not domain and state.user_keywords:
            for d, cues in DOMAIN_HINTS.items():
                if any(cue in state.user_keywords for cue in cues):
                    domain = d
                    break
        
        domain = domain or DOMAIN_PRIORITY[0]

        today = (
            "오늘은 짧게 상황을 한 문장으로 정리해두세요. 예) \"월세 연체 걱정, 이번 달 생활비 부족\". "
            "이 문장을 가지고 전화·상담을 시작하면 부담이 줄어요."
        )

        tomorrow = (
            f"내일은 {domain} 쪽으로 '지원 가능성만 먼저 확인하고 싶다'고 문의해보세요. "
            "지역(시/군/구)만 알려주면 더 빨라지지만, 지금은 전국 공통 경로부터 살펴보셔도 괜찮습니다."
        )

        stuck = (
            "연결이 어렵거나 답을 못 들으면, '신청'이 아니라 '자격 확인 상담'만 먼저 부탁한다고 말해보세요. "
            "서류가 없어도 현재 상황만 말하고 가볍게 시작하셔도 됩니다."
        )

    return {"today": today, "tomorrow": tomorrow, "stuck": stuck}
