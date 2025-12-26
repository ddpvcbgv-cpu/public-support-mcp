"""
확장 가능성 안내 및 후속 제안 도구
"""
from __future__ import annotations

from typing import Dict, List

from state import SessionState
from constants import REQUIRED_PHRASES


def suggest_followup_options(state: SessionState) -> Dict[str, object]:
    """
    현재 상황을 기반으로 추가 탐색 가능한 지원 분야를 제안합니다.
    
    Args:
        state: 세션 상태
    
    Returns:
        확장 가능성 안내 및 후속 제안
    """
    # 이미 탐색한 분야
    explored_domain = state.chosen_domain
    
    # 전체 분야 목록
    all_domains = ["주거·월세", "생활 유지", "의료·돌봄", "고용·교육", "심리·정서"]
    
    # 아직 탐색하지 않은 분야
    unexplored = [d for d in all_domains if d != explored_domain]
    
    # 사용자 키워드 기반으로 관련성 높은 분야 우선순위
    priority_domains = _prioritize_domains(state.user_keywords, unexplored)
    
    # 상황별 추천
    recommendations = []
    
    # 긴급도가 높으면 생활 유지 + 주거 병행 제안
    if state.urgency_level <= 2:
        if "생활 유지" in priority_domains and explored_domain != "생활 유지":
            recommendations.append({
                "domain": "생활 유지",
                "reason": "긴급한 상황에서는 당장의 생활비 확보도 함께 살펴보는 것이 도움이 될 수 있어요."
            })
        if "주거·월세" in priority_domains and explored_domain != "주거·월세":
            recommendations.append({
                "domain": "주거·월세",
                "reason": "주거 안정이 우선될 때, 다른 지원도 연결이 더 쉬워지는 경우가 많아요."
            })
    
    # 일반적인 경우: 키워드 기반 TOP 2
    if not recommendations:
        for domain in priority_domains[:2]:
            recommendations.append({
                "domain": domain,
                "reason": f"지금 상황을 보면 {domain} 쪽도 함께 확인해볼 여지가 있어요."
            })
    
    return {
        "expansion_message": REQUIRED_PHRASES["expansion"],
        "recommendations": recommendations[:2],  # 최대 2개만
        "explored_domain": explored_domain,
        "total_unexplored": len(unexplored),
    }


def _prioritize_domains(keywords: List[str], domains: List[str]) -> List[str]:
    """
    키워드 기반으로 도메인 우선순위를 정렬합니다.
    
    Args:
        keywords: 사용자 키워드 목록
        domains: 탐색 가능한 도메인 목록
    
    Returns:
        우선순위가 정렬된 도메인 목록
    """
    from tools.domains import DOMAIN_HINTS
    
    # 각 도메인의 점수 계산
    domain_scores = {}
    for domain in domains:
        score = 0
        hints = DOMAIN_HINTS.get(domain, [])
        for keyword in keywords:
            if any(hint in keyword for hint in hints):
                score += 1
        domain_scores[domain] = score
    
    # 점수 순으로 정렬
    sorted_domains = sorted(domains, key=lambda d: domain_scores.get(d, 0), reverse=True)
    
    return sorted_domains

