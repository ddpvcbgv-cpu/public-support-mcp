from __future__ import annotations

from enum import Enum
from typing import Literal, TypedDict, Optional, Dict, Any

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


class RiskLevel(str, Enum):
    NONE = "NONE"
    LEVEL_1 = "LEVEL_1"  # 즉시 위험 (자살/극단적 폭력)
    LEVEL_2 = "LEVEL_2"  # 심각한 위기이지만 즉시 생명 위협은 아님


class RiskType(str, Enum):
    NONE = "NONE"
    SELF_HARM = "SELF_HARM"  # 자살·자해
    VIOLENCE = "VIOLENCE"  # 성폭력/가정폭력/데이트폭력 등
    BULLYING_OR_STRESS = "BULLYING_OR_STRESS"  # 왕따/학교폭력/심각한 괴롭힘·압박


class SafetyRisk(TypedDict):
    level: RiskLevel
    type: RiskType
    raw_match: Optional[str]


def detect_safety_risk(message: str) -> SafetyRisk:
    """
    사용자 발화에서 자살·폭력·왕따 등 안전 리스크를 감지한다.

    반환값:
        level:
            - LEVEL_1: 즉시 안전이 최우선 (자살, 가족 성폭력 등)
            - LEVEL_2: 심각한 위기 (왕따, 학교폭력, 데이트폭력, 심각한 괴롭힘 등)
            - NONE: 별도 안전 플로우 없이 일반 플로우 진행
        type:
            - SELF_HARM / VIOLENCE / BULLYING_OR_STRESS / NONE
        raw_match:
            - 매칭된 키워드 (디버깅용)
    """
    text = (message or "").lower().strip()

    # 1) 자살·자해 관련 (무조건 LEVEL_1)
    self_harm_keywords = [
        "죽고 싶", "죽고싶", "살기 싫", "살기싫",
        "극단적인 선택", "극단적 선택",
        "목매", "목을 매", "뛰어내리", "투신",
        "손목 그었", "자해", "피 흘리", "피흘리",
        "더 살고 싶지 않", "존재가치가 없", "없어졌으면 좋겠",
    ]
    for kw in self_harm_keywords:
        if kw in text:
            return {
                "level": RiskLevel.LEVEL_1,
                "type": RiskType.SELF_HARM,
                "raw_match": kw,
            }

    # 2) 폭력·성폭력 관련
    #    - 가족/보호자/연인 + 성폭행/폭력 → LEVEL_1
    #    - 그 외 폭력/데이트폭력/가정폭력 → LEVEL_2
    violence_keywords = [
        "성폭행", "성 폭행", "강간", "강제", "강제로 만져",
        "성추행", "성 추행", "추행", "몸을 만졌",
        "강제로 키스", "원치 않는데", "원하지 않았는데",
        "때려요", "맞아요", "폭행", "폭력", "학대", "괴롭혀요",
        "가정폭력", "데이트폭력", "데이트 폭력",
    ]
    family_or_partner_keywords = [
        "부모", "부모님", "아버지", "아빠", "어머니", "엄마",
        "오빠", "형", "남동생", "언니", "누나", "여동생",
        "삼촌", "고모", "이모", "친척",
        "남자친구", "여자친구", "남친", "여친", "애인",
        "남편", "아내",
        "가족",
    ]

    violence_hit = None
    for kw in violence_keywords:
        if kw in text:
            violence_hit = kw
            break

    if violence_hit:
        is_family_or_partner = any(kw in text for kw in family_or_partner_keywords)
        if is_family_or_partner:
            # 예: "부모님이 저를 성폭행해요", "남자친구가 때려요"
            return {
                "level": RiskLevel.LEVEL_1,
                "type": RiskType.VIOLENCE,
                "raw_match": violence_hit,
            }
        else:
            # 그 외 폭력/괴롭힘 → LEVEL_2
            return {
                "level": RiskLevel.LEVEL_2,
                "type": RiskType.VIOLENCE,
                "raw_match": violence_hit,
            }

    # 3) 왕따·학교폭력·심각한 괴롭힘 (LEVEL_2)
    bullying_keywords = [
        "왕따", "왕 따", "따돌림", "따 돌림",
        "학교폭력", "학교 폭력", "학교에서 폭력",
        "괴롭힘", "괴롭혀요", "놀려요", "집단으로",
        "무시당해", "무시 당해", "소외", "따 시켜",
        "폭언", "욕을 먹", "욕설", "언어폭력", "언어 폭력",
        "직장 내 괴롭힘", "직장 괴롭힘", "직장폭력",
    ]
    stress_keywords = [
        "숨 막혀", "숨막혀", "버티기 힘들", "버티기 너무 힘들",
        "너무 힘들어요", "너무 힘들어", "견디기 힘들",
        "마음이 무너져", "정신적으로 너무 힘들",
        "사는 게 의미 없", "살 이유를 모르겠",
        "잠이 안 와", "잠이 안와", "불안해서 못 자",
    ]
    for kw in bullying_keywords + stress_keywords:
        if kw in text:
            return {
                "level": RiskLevel.LEVEL_2,
                "type": RiskType.BULLYING_OR_STRESS,
                "raw_match": kw,
            }

    return {
        "level": RiskLevel.NONE,
        "type": RiskType.NONE,
        "raw_match": None,
    }


def build_level1_self_harm_message() -> str:
    """
    자살·자해 관련 즉시 위험 상황용 안내.
    온보딩/분야 안내 없이 바로 안전 안내만 한다.
    """
    return (
        "지금 말씀하신 내용은, 스스로를 해치고 싶거나\n"
        "극단적인 선택을 떠올릴 정도로 힘든 상황으로 들려요.\n"
        "이 말을 꺼내는 것 자체가 이미 엄청난 용기예요.\n\n"
        "지금 이 순간에는 '정확한 제도'보다도, "
        "'당신이 오늘을 넘길 수 있게 같이 버티는 것'이 더 중요해요.\n\n"
        "지금 할 수 있는 가장 안전한 선택 몇 가지만 바로 적어볼게요.\n\n"
        "1️⃣ 혼자 있는 공간이라면, 잠시라도 안전한 곳(문을 열어두거나, "
        "신뢰할 수 있는 사람 근처)으로 이동해 주세요.\n\n"
        "2️⃣ 한국에서는 24시간 연결 가능한 전화들이 있어요.\n"
        "   • 자살예방 상담전화 1393 (24시간, 무료, 익명 가능)\n"
        "   • 정신건강 위기상담 1577-0199\n"
        "   • 응급 상황이 의심되면 112 또는 119\n\n"
        "지금 바로 전화를 걸지 못하겠다면,\n"
        "이 대화 안에서라도 '오늘을 넘기기 위해 필요한 것'부터 같이 적어볼 수 있어요.\n"
        "지금 여기까지 써주신 걸로도, 당신은 이미 완전히 혼자는 아니에요."
    )


def build_level1_violence_message() -> str:
    """
    가족 성폭력/가정폭력/데이트폭력 등 즉시 안전이 우선인 상황용 안내.
    """
    return (
        "지금 말씀해주신 내용은, 아주 심각한 폭력·학대 상황으로 들려요.\n"
        "특히 가까운 사람(가족·연인 등)에게서 이런 일을 겪고 있다면,\n"
        "이건 절대 당신 탓이 아니고, 혼자 감당해야 할 일이 아니에요.\n\n"
        "지금은 '정확한 복지 제도'보다도, "
        "'당신의 몸과 마음을 당장 더 다치지 않게 하는 것'이 먼저예요.\n\n"
        "가능하다면 아래 중 하나를 시도해볼 수 있어요:\n\n"
        "1️⃣ 지금 위험이 계속되고 있거나, 당장 또 폭력이 반복될 것 같다면\n"
        "   → 112로 전화해서 '가정폭력/성폭력 피해자'라고만 말씀하셔도 됩니다.\n\n"
        "2️⃣ 바로 신고가 부담된다면\n"
        "   • 긴급전화 1366 (여성긴급상담, 24시간)\n"
        "   • 117 (학교폭력·아동학대·가정폭력 신고·상담)\n"
        "   으로 '지금 집에서 이런 일을 겪고 있다'고만 말해도, "
        "상담사가 다음 단계를 같이 잡아줍니다.\n\n"
        "이 상황에서 느끼는 두려움과 혼란은 너무나 자연스러운 반응이에요.\n"
        "지금은 당신이 혼자 버티는 대신, "
        "조금이라도 안전 쪽으로 한 걸음만 옮겨보는 게 제일 중요해요."
    )


def build_level2_bullying_or_stress_message(risk: SafetyRisk) -> str:
    """
    왕따·학교폭력·직장 내 괴롭힘·심각한 정서 압박 등 LEVEL_2 상황용 안내.
    온보딩 전체 대신, 짧은 공감 + 다음 단계 힌트만 준다.
    """
    base = (
        "지금 말씀해주신 걸 보면, 혼자 감당하기엔 너무 벅찰 정도의 상황으로 느껴져요.\n"
        "왕따, 학교폭력, 괴롭힘, 반복되는 폭언 같은 일들은\n"
        "사람의 자존감과 일상 전체를 뒤흔들 수 있는 일이라서, "
        "지금 느끼는 감정이 전혀 과한 게 아니에요.\n\n"
        "우선, '이게 괜히 내가 예민한 건가?'라고 스스로를 탓하지 않으셨으면 좋겠어요.\n"
    )

    follow = (
        "\n이런 상황에서는 보통 두 가지 축으로 동시에 보는 게 도움이 돼요.\n"
        "1️⃣ 지금 당장, 반복되는 상황에서 내가 잠시라도 벗어날 수 있는 안전한 공간/사람\n"
        "2️⃣ 학교·직장·지역에서 공식적으로 도움을 줄 수 있는 창구(상담실, 위기센터 등)\n\n"
        "조금만 여유가 되신다면, 아래 중에서 편한 것부터 하나만 알려주실 수 있을까요?\n"
        "• 학교 / 직장 / 가정 / 온라인 공간 중 어디에서 주로 일이 벌어지고 있나요?\n"
        "• 지금 가장 두려운 건 '앞으로 계속 이 상황이 반복되는 것'인가요,\n"
        "  아니면 '지금 이 자리에서 당장 벌어질 일'인가요?\n\n"
        "이걸 알아야, 다음에 어떤 지원(학교폭력 신고, 상담, 쉼 공간 등)을 같이 볼지 정하기가 조금 쉬워져요."
    )

    return base + follow


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
