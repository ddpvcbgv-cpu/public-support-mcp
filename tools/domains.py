from __future__ import annotations

from typing import Dict, List

from state import SessionState


DOMAIN_PRIORITY = ["주거·월세", "생활 유지", "의료·돌봄", "고용·교육", "심리·정서"]

DOMAIN_HINTS: Dict[str, List[str]] = {
    "주거·월세": ["월세", "전세", "보증금", "집", "퇴거", "이사", "쫓겨"],
    "생활 유지": ["생활비", "생계", "공과금", "연체", "관리비", "식비"],
    "의료·돌봄": ["병원", "의료", "건강", "약값", "수술", "돌봄", "간병", "장애"],
    "고용·교육": ["취업", "구직", "교육", "훈련", "일자리", "이직", "실업", "알바", "근로"],
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


def expose_available_domains(state: SessionState) -> Dict[str, List[str]]:
    """상황에 맞는 분야 목록을 제안한다."""
    matched: List[str] = []
    for domain, cues in DOMAIN_HINTS.items():
        if any(cue in state.user_keywords for cue in cues):
            matched.append(domain)

    if not matched:
        matched = DOMAIN_PRIORITY[:3]

    domains = _deduplicate(matched)[:5]
    return {"domains": domains}
