from __future__ import annotations

import re
from typing import Dict, List

from state import ConversationPhase, SessionState


THEME_KEYWORDS: Dict[str, List[str]] = {
    "주거·월세": ["월세", "전세", "보증금", "집", "퇴거", "이사", "쫓겨"],
    "생활 유지": ["생활비", "생계", "공과금", "연체", "관리비", "식비", "알바", "아르바이트", "소득"],
    "의료·돌봄": ["병원", "의료", "건강", "진료", "약값", "수술", "돌봄", "간병", "장애", "아이", "육아"],
    "고용·교육": ["취업", "구직", "교육", "훈련", "일자리", "이직", "실업", "근로"],
    "심리·정서": ["우울", "불안", "상담", "스트레스"],
}


def _deduplicate(items: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def normalize_user_context(message: str, state: SessionState) -> Dict[str, object]:
    """정제된 요약과 키워드를 반환하고 세션 상태를 업데이트."""
    # 🆕 대화 히스토리 업데이트
    from tools.intent import update_conversation_history
    from tools.scoring import update_user_profile_from_keywords
    
    extracted: List[str] = []
    for keywords in THEME_KEYWORDS.values():
        for word in keywords:
            if word and word in message:
                extracted.append(word)

    merged_keywords = _deduplicate(state.user_keywords + extracted)
    state.user_keywords = merged_keywords

    # 🆕 대화 히스토리에 추가
    update_conversation_history(message, state, keywords=extracted)
    
    # 🆕 사용자 프로파일 업데이트
    update_user_profile_from_keywords(state)

    if extracted:
        sample = ", ".join(extracted[:3])
        summary = f"지금 말씀하신 내용을 정리하면, {sample} 같은 부분을 걱정하고 계신 걸로 메모해둘게요. 평가 없이 필요한 부분만 차근차근 살펴보면 좋겠어요."
    else:
        summary = "지금 말씀을 정리했어요. 편한 만큼만 더 알려주시면 연결 경로를 조금 더 구체화해볼게요."

    return {"summary": summary, "keywords": merged_keywords}


# 🆕 v2: 카드 텍스트 안전화를 위한 키워드 리스트
POLICY_NAME_KEYWORDS = [
    # 급여 제도
    "생계급여", "주거급여", "의료급여", "교육급여",
    # 긴급 지원
    "긴급복지지원", "에너지바우처",
    # 문화/교통
    "문화누리카드", "기후동행카드", "청년문화패스",
    # 교육/고용
    "내일배움카드", "K-MOOC",
    # 자격 조건
    "기초생활수급자", "차상위계층",
]

INSTITUTION_NAME_KEYWORDS = [
    "복지로",  # 연락처 맥락이 아니면 제거
    # "주민센터"는 연락처 맥락에서는 유지
]

RESULT_PHRASES = [
    "대상입니다", "받을 수 있어요", "확정 지원", "지원 가능",
    "대상이에요", "받을 수 있습니다", "지원됩니다",
]


def sanitize_card_text(text: str, phase: ConversationPhase) -> str:
    """
    카드 텍스트에서 제도명/기관명을 제거하거나 마스킹합니다.
    
    Args:
        text: 원본 카드 텍스트
        phase: 현재 대화 단계
    
    Returns:
        안전화된 텍스트
    """
    sanitized = text
    
    # PRE_DECISION 단계에서는 모든 제도명/기관명 제거
    if phase == ConversationPhase.PRE_DECISION:
        # 제도명 제거
        for keyword in POLICY_NAME_KEYWORDS:
            sanitized = sanitized.replace(keyword, "[제도명]")
        
        # 기관명 처리 (연락처 맥락 제외)
        # "📞 복지로 129" 같은 패턴은 유지, 단독 언급만 제거
        sanitized = re.sub(r'(?<!📞\s)(?<!전화\s)(?<!연락\s)복지로(?!\s\d)', '[기관명]', sanitized)
        
        # 결과 암시 제거
        for phrase in RESULT_PHRASES:
            sanitized = sanitized.replace(phrase, "")
        
        # 금액 정보 제거
        sanitized = re.sub(r'\d+만원|\d+원|월\s*\d+만원', '[금액]', sanitized)
    
    # DIRECTION_SELECTED 이상에서는 제도명은 유지하되, 조건/결과 암시만 제거
    elif phase >= ConversationPhase.DIRECTION_SELECTED:
        # 금액 정보 제거
        sanitized = re.sub(r'\d+만원|\d+원|월\s*\d+만원', '[금액]', sanitized)
        
        # 결과 암시 제거
        for phrase in RESULT_PHRASES:
            sanitized = sanitized.replace(phrase, "")
    
    return sanitized.strip()

