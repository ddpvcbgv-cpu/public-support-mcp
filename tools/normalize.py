from __future__ import annotations

from typing import Dict, List

from state import SessionState


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
    extracted: List[str] = []
    for keywords in THEME_KEYWORDS.values():
        for word in keywords:
            if word and word in message:
                extracted.append(word)

    merged_keywords = _deduplicate(state.user_keywords + extracted)
    state.user_keywords = merged_keywords

    if extracted:
        sample = ", ".join(extracted[:3])
        summary = f"지금 말씀하신 내용을 정리하면, {sample} 같은 부분을 걱정하고 계신 걸로 메모해둘게요. 평가 없이 필요한 부분만 차근차근 살펴보면 좋겠어요."
    else:
        summary = "지금 말씀을 정리했어요. 편한 만큼만 더 알려주시면 연결 경로를 조금 더 구체화해볼게요."

    return {"summary": summary, "keywords": merged_keywords}

