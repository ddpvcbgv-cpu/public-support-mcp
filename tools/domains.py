from __future__ import annotations

from typing import Dict, List

from state import SessionState


DOMAIN_PRIORITY = ["주거·월세", "생활 유지", "의료·돌봄", "고용·교육", "심리·정서"]

# 🆕 확장 도메인: 사용자가 명시적으로 요청할 때만 활성화
EXTENDED_DOMAINS = ["문화·여가", "평생교육", "참여·활동"]

DOMAIN_HINTS: Dict[str, List[str]] = {
    # 핵심 도메인 (기본 노출)
    "주거·월세": ["월세", "전세", "보증금", "집", "퇴거", "이사", "쫓겨"],
    "생활 유지": ["생활비", "생계", "공과금", "연체", "관리비", "식비"],
    "의료·돌봄": ["병원", "의료", "건강", "약값", "수술", "돌봄", "간병", "장애"],
    "고용·교육": ["취업", "구직", "교육", "훈련", "일자리", "이직", "실업", "알바", "근로"],
    "심리·정서": ["우울", "불안", "상담", "스트레스"],
    
    # 🆕 확장 도메인 (키워드 매칭 시에만 노출)
    "문화·여가": ["문화", "여가", "공연", "영화", "도서", "체육", "취미", "전시", "관람"],
    "평생교육": ["배우고", "공부", "학습", "강좌", "수업", "강의", "평생교육"],
    "참여·활동": ["봉사", "참여", "모임", "커뮤니티", "활동", "동아리", "네트워크"],
}


def _deduplicate(items: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def expose_available_domains(state: SessionState) -> Dict[str, List[str]]:
    """상황에 맞는 분야 목록을 제안한다.
    
    기본: 핵심 도메인(주거·생활·의료·고용·심리)만 노출
    확장: 사용자가 명시적 키워드 사용 시 확장 도메인도 노출
    """
    matched: List[str] = []
    basic_matched: List[str] = []
    extended_matched: List[str] = []
    
    for domain, cues in DOMAIN_HINTS.items():
        if any(cue in state.user_keywords for cue in cues):
            if domain in DOMAIN_PRIORITY:
                basic_matched.append(domain)
            elif domain in EXTENDED_DOMAINS:
                extended_matched.append(domain)
    
    # 기본 도메인 우선, 확장 도메인은 명시적 요청 시만
    matched = basic_matched
    if extended_matched:
        # 확장 도메인이 매칭되면 추가 (사용자가 직접 언급함)
        matched.extend(extended_matched)

    if not matched:
        # 키워드 매칭 실패 시 기본 3개
        matched = DOMAIN_PRIORITY[:3]

    domains = _deduplicate(matched)[:5]
    
    # 🆕 스마트 제안: 기본 도메인만 있고 긴급하지 않으면 확장 힌트
    smart_suggestion = None
    if not extended_matched and state.urgency_level >= 3:
        smart_suggestion = "생활 안정 관련 지원을 우선 살펴보시고, 이후 문화·교육 같은 영역도 함께 확인하실 수 있어요."
    
    return {
        "domains": domains,
        "smart_suggestion": smart_suggestion
    }
