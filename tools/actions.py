from __future__ import annotations

from typing import Dict, Optional

from state import SessionState


def generate_action_steps(state: SessionState, domain: Optional[str] = None) -> Dict[str, str]:
    """
    지금 바로 할 수 있는 1~3단계 행동을 제안한다.

    - 가능한 경우: 방금 본 카드(state.shown_cards 마지막)를 기준으로 오늘/내일/막히면 구성
    - 그렇지 않은 경우: domain(또는 state.chosen_domain)에 따라 도메인별 템플릿 사용
    - 도메인을 특정하기 어려우면: 비교적 안전한 generic 템플릿 사용
    """
    from tools.domains import DOMAIN_HINTS, DOMAIN_PRIORITY
    from tools.cards import CARD_LIBRARY

    # 1) domain 인자 또는 state에서 현재 도메인 추론
    current_domain = (domain or state.chosen_domain or "").strip()

    # 2) 가장 최근에 본 카드가 있으면, 그 카드 기반으로 액션 단계 구성
    target_card = None
    if getattr(state, "shown_cards", None):
        for card_name in reversed(state.shown_cards):
            for domain_cards in CARD_LIBRARY.values():
                for card in domain_cards:
                    if card.get("card") == card_name:
                        target_card = card
                        break
                if target_card:
                    break
            if target_card:
                break

    if target_card:
        say_phrase = target_card.get("지금_하실_수_있는_말", "").strip()
        where_info = (target_card.get("where") or "").strip()
        how_info = (target_card.get("how") or "").strip()
        stuck_info = (target_card.get("막히면") or "").strip()

        # 카드 기반 액션 단계 (도메인 공통)
        today = (
            "오늘은 너무 길게 준비하지 않으셔도 괜찮아요. "
            "상담이나 전화를 시작할 때 이렇게 한 문장만 준비해두시면 좋아요.\n"
            f"예) \"{say_phrase or '지금 상황을 먼저 상담만 받아보고 싶어요.'}\""
        )

        tomorrow = (
            "내일은 아래 기관 중 한 곳을 정해서, 오늘 적어둔 문장을 그대로 읽어보세요.\n"
            f"{where_info or '가까운 주민센터나 상담 창구'}\n"
            f"전화나 방문 시에는, '{(how_info.split('1)')[0] if how_info else '지원 가능성만 먼저 확인받고 싶다'}'"
            " 라고 덧붙이셔도 좋습니다."
        )

        stuck = (
            stuck_info
            or "연결이 어렵거나 자격이 애매하다고 들리면, "
               "'신청'이 아니라 '자격 가능성 상담만 먼저 받고 싶다'고 말씀해보세요. "
               "서류가 다 준비되지 않아도, 현재 상황만 말씀드리고 가볍게 시작하셔도 됩니다."
        )

        return {"today": today, "tomorrow": tomorrow, "stuck": stuck}

    # 3) 카드 기반이 없을 때 → 도메인 기준 템플릿 분기

    # 도메인 없으면 user_keywords 기반으로 추론 시도
    if not current_domain and getattr(state, "user_keywords", None):
        try:
            for d, cues in DOMAIN_HINTS.items():
                if any(cue in state.user_keywords for cue in cues):
                    current_domain = d
                    break
        except Exception:
            pass

    # 그래도 없으면 최우선 도메인으로
    if not current_domain:
        current_domain = DOMAIN_PRIORITY[0] if DOMAIN_PRIORITY else "생활 유지"

    cd = current_domain  # 축약

    # === A 레벨: 반드시 손으로 짠 도메인 (정밀 템플릿) ===

    # 3-1) 의료·돌봄
    if ("의료" in cd) or ("돌봄" in cd):
        today = (
            "오늘은 병원 사회복지과나 보건복지상담센터(129)에 짧게라도 연락해보는 걸 1순위로 두시면 좋겠어요.\n"
            "예) \"가족을 돌보는 데 병원비/돌봄비가 부담돼서, 지원 가능성만 먼저 상담받고 싶어요.\""
        )
        tomorrow = (
            "내일은 국민건강보험공단(1577-1000)이나 긴급의료비 지원 재단에 문의해보세요.\n"
            "진료비 상한제(본인부담상한제)나 긴급의료비 지원 대상이 될 수 있는지 "
            "‘신청’이 아니라 ‘자격 가능성 확인’만 먼저 부탁하셔도 됩니다."
        )
        stuck = (
            "병원에서 어디로 연결해야 할지 모호하게 말할 때는, 원무과나 접수창구에 "
            "\"사회복지사 선생님과 상담하고 싶어요\"라고만 말씀해보셔도 괜찮아요. "
            "서류를 다 못 챙겨도, 현재 상황을 먼저 들려주는 것만으로도 시작이 됩니다."
        )
        return {"today": today, "tomorrow": tomorrow, "stuck": stuck}

    # 3-2) 주거·월세
    if ("주거" in cd) or ("월세" in cd):
        today = (
            "오늘은 지금 가장 부담되는 지점을 한 문장으로만 적어두세요.\n"
            "예) \"월세 연체 걱정, 이번 달 보증금·관리비가 너무 부담됩니다.\""
        )
        tomorrow = (
            "내일은 거주지 주민센터(행정복지센터)나 보건복지상담센터(129)에 전화해서 이렇게 말씀해보세요.\n"
            "\"지금 월세/주거비가 부담돼서, 주거 지원(주거급여·긴급지원 등) 가능성만 먼저 상담받고 싶어요.\""
        )
        stuck = (
            "상담 창구에서 '기준이 안 된다'고만 말하면, "
            "\"그럼 제가 주거·월세와 관련해서 다른 지원(긴급복지, 공공임대, 이사 지원 등) 중에 "
            "가능성이 있는 게 있는지 한 번만 더 확인해 주세요\"라고 덧붙여 보세요."
        )
        return {"today": today, "tomorrow": tomorrow, "stuck": stuck}

    # 3-3) 생활 유지 (생활비/공과금/식비)
    if ("생활" in cd) or ("유지" in cd) or ("생계" in cd):
        today = (
            "오늘은 생활비 때문에 가장 힘든 지점을 한 문장으로 적어두세요.\n"
            "예) \"이번 달 공과금·식비가 감당이 안 됩니다.\""
        )
        tomorrow = (
            "내일은 보건복지상담센터(129)나 주민센터에 전화해서 이렇게 말씀해보세요.\n"
            "\"생활비 때문에 힘든데, 생계급여나 긴급복지 같은 지원이 가능한지 상담만 먼저 받고 싶어요.\""
        )
        stuck = (
            "‘대상이 아니다’라는 답만 들리면, "
            "\"그럼 생계급여가 아니더라도 긴급복지나 기타 생활비 완충 제도가 있는지, "
            "가능성만 한 번 더 확인해 주세요\"라고 조심스럽게 부탁해 보셔도 됩니다."
        )
        return {"today": today, "tomorrow": tomorrow, "stuck": stuck}

    # 3-4) 고용·교육 (취업/직업훈련)
    if ("고용" in cd) or ("교육" in cd) or ("취업" in cd) or ("훈련" in cd):
        today = (
            "오늘은 하고 싶은 일이나 관심 있는 직무를 한 줄로만 적어보세요.\n"
            "예) \"콘텐츠 관련 일\", \"사무 보조\", \"요양보호사\" 등, 아주 거칠어도 괜찮습니다."
        )
        tomorrow = (
            "내일은 고용센터(1350)나 온라인 Work24/HRD-Net에 접속해서,\n"
            "\"지금 상황에서 받을 수 있는 취업지원제도나 직업훈련이 뭐가 있는지 상담만 먼저 받고 싶어요\"라고 "
            "문의해보세요. ‘어떤 교육이 좋은지’보다는 ‘내 상황에 맞는 경로가 뭐가 있는지’에 초점을 맞추면 좋아요."
        )
        stuck = (
            "상담이 복잡하게 느껴지면, "
            "\"국민취업지원제도 대상이 될 수 있는지, 그리고 제 상황에 맞는 직업훈련 한두 개만 "
            "추천해 주실 수 있을까요?\"라고 구체적으로 요청해 보셔도 좋습니다."
        )
        return {"today": today, "tomorrow": tomorrow, "stuck": stuck}

    # 3-5) 심리·정서
    if ("심리" in cd) or ("정서" in cd) or ("마음" in cd):
        today = (
            "오늘은 혼자 견디지 않기 위한 첫걸음으로, 24시간 가능한 상담전화에 한 번만 연결해 보셔도 좋아요.\n"
            "정신건강위기상담 1577-0199, 자살예방상담 1393, 청소년이라면 1388도 있습니다.\n"
            "연결되면 \"요즘 너무 힘들어서, 그냥 잠깐 얘기만 들어주시면 좋겠어요\"라고만 시작하셔도 괜찮아요."
        )
        tomorrow = (
            "내일은 거주지 보건소 정신건강복지센터나 청소년상담복지센터를 검색해서,\n"
            "\"지속적인 무료/저렴한 상담이 가능한지\" 문의해보세요. "
            "전화로만 먼저 상담 예약을 잡아도 충분한 시작입니다."
        )
        stuck = (
            "전화가 너무 버겁다면, 문자/채팅 상담이나 온라인 익명 상담부터 시작하셔도 됩니다. "
            "중요한 건 혼자서 전부 버티지 않아도 된다는 걸 한번만 몸으로 느껴보는 거예요."
        )
        return {"today": today, "tomorrow": tomorrow, "stuck": stuck}

    # === B/C 레벨: 기타 도메인 (문화·여가 등) → 비교적 안전한 generic 템플릿 ===

    # 문화·여가, 평생교육, 기타
    if ("문화" in cd) or ("여가" in cd):
        today = (
            "오늘은 '문화생활을 못 해서 힘든 점'을 한 문장으로 적어보세요.\n"
            "예) \"밖에 나가고 싶지만 돈이 부담돼서 집에만 있게 됩니다.\""
        )
        tomorrow = (
            "내일은 주민센터나 가까운 문화·복지관에 문의해서, "
            "\"문화누리카드나 지역 문화지원(공연/영화/강좌 할인·무료 프로그램)이 있는지\" "
            "가능성만 먼저 물어보세요."
        )
        stuck = (
            "직접 방문이 부담되면, 복지로 사이트나 지자체 홈페이지에서 "
            "\"문화누리카드\", \"청년문화패스\", \"문화바우처\" 같은 키워드로 한 번만 천천히 살펴보셔도 좋습니다."
        )
        return {"today": today, "tomorrow": tomorrow, "stuck": stuck}

    # 알 수 없는 / 기타 도메인: 최대한 중립적인 generic 템플릿
    today = (
        "오늘은 지금 가장 걱정되는 부분을 한 문장으로만 적어두세요.\n"
        "예) \"이번 달이 특히 걱정됩니다\", \"혼자 감당하기 버겁습니다\" 같은 문장만으로도 충분해요."
    )
    tomorrow = (
        "내일은 거주지 기준으로 가장 가까운 공공 창구(주민센터, 보건복지상담센터 129 등)에 연락해서,\n"
        "\"지금 말씀드린 상황에 맞는 공공 지원이 있는지, 신청이 아니라 '가능성 상담'만 먼저 받고 싶어요\"라고 "
        "말씀해보세요."
    )
    stuck = (
        "여러 번 전화나 방문이 부담되면, 주변의 사회복지관·복지센터·상담기관 중 한 곳만 골라 "
        "현재 상황을 들려주고 '어디로 가야 할지' 길잡이 역할만 요청하셔도 괜찮습니다."
    )

    return {"today": today, "tomorrow": tomorrow, "stuck": stuck}
