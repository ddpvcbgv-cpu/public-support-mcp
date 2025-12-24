"""스코어링 시스템 - 사용자 프로파일 기반 혜택 매칭"""
from __future__ import annotations

from typing import Dict, List

from schemas import UserProfile
from state import SessionState


# 혜택별 메타데이터 (실제로는 데이터베이스나 API에서 가져와야 함)
BENEFIT_METADATA: Dict[str, Dict[str, any]] = {
    "주거 안심 상담": {
        "urgency_match": [1, 2, 3],  # 모든 긴급도에 적합
        "keywords": ["월세", "전세", "보증금", "집", "퇴거"],
        "min_age": 0,
        "max_age": 999,
        "priority": 1,  # 우선순위 (낮을수록 높음)
    },
    "체납 완화 점검": {
        "urgency_match": [1, 2],
        "keywords": ["연체", "공과금", "관리비"],
        "min_age": 0,
        "max_age": 999,
        "priority": 2,
    },
    "안전 이사 대비": {
        "urgency_match": [1],
        "keywords": ["쫓겨", "퇴거", "이사"],
        "min_age": 0,
        "max_age": 999,
        "priority": 1,
    },
    "생활비 숨통 점검": {
        "urgency_match": [1, 2, 3],
        "keywords": ["생활비", "생계", "식비"],
        "min_age": 0,
        "max_age": 999,
        "priority": 1,
    },
    "연체 리듬 조정": {
        "urgency_match": [1, 2],
        "keywords": ["연체", "밀린"],
        "min_age": 0,
        "max_age": 999,
        "priority": 2,
    },
    "식비·생필품 완충": {
        "urgency_match": [1, 2],
        "keywords": ["식비", "생필품", "굶"],
        "min_age": 0,
        "max_age": 999,
        "priority": 1,
    },
    "진료비 부담 점검": {
        "urgency_match": [1, 2, 3],
        "keywords": ["병원", "의료", "진료", "약값"],
        "min_age": 0,
        "max_age": 999,
        "priority": 1,
    },
    "돌봄 공백 메우기": {
        "urgency_match": [1, 2],
        "keywords": ["돌봄", "간병", "아이", "육아"],
        "min_age": 0,
        "max_age": 999,
        "priority": 2,
    },
    "의료비 지출 계획": {
        "urgency_match": [2, 3],
        "keywords": ["수술", "치료", "병원비"],
        "min_age": 0,
        "max_age": 999,
        "priority": 2,
    },
    "소득 회복 탐색": {
        "urgency_match": [2, 3],
        "keywords": ["취업", "구직", "일자리", "실직"],
        "min_age": 18,
        "max_age": 70,
        "priority": 1,
    },
    "경험 전환 지원": {
        "urgency_match": [3],
        "keywords": ["이직", "교육", "훈련"],
        "min_age": 18,
        "max_age": 65,
        "priority": 2,
    },
    "근로 권리 점검": {
        "urgency_match": [2, 3],
        "keywords": ["근로", "권리", "체불"],
        "min_age": 15,
        "max_age": 999,
        "priority": 2,
    },
    "마음 긴급 완충": {
        "urgency_match": [1, 2],
        "keywords": ["우울", "불안", "스트레스"],
        "min_age": 0,
        "max_age": 999,
        "priority": 1,
    },
    "지지 자원 연결": {
        "urgency_match": [2, 3],
        "keywords": ["상담", "혼자"],
        "min_age": 0,
        "max_age": 999,
        "priority": 2,
    },
}


def calculate_eligibility_score(
    benefit_name: str,
    state: SessionState,
) -> int:
    """혜택과 사용자 상태의 적합도 점수 계산 (0~100)"""
    metadata = BENEFIT_METADATA.get(benefit_name)
    if not metadata:
        return 50  # 메타데이터 없으면 중간 점수
    
    score = 0
    
    # 1. 긴급도 매칭 (30점)
    if state.urgency_level in metadata["urgency_match"]:
        score += 30
    
    # 2. 키워드 매칭 (40점)
    benefit_keywords = set(metadata["keywords"])
    user_keywords = set(state.user_keywords)
    overlap = benefit_keywords & user_keywords
    
    if benefit_keywords:
        keyword_score = (len(overlap) / len(benefit_keywords)) * 40
        score += int(keyword_score)
    
    # 3. 우선순위 보너스 (20점)
    priority = metadata.get("priority", 3)
    if priority == 1:
        score += 20
    elif priority == 2:
        score += 10
    
    # 4. 대화 히스토리 기반 보너스 (10점)
    if state.conversation_history:
        # 최근 대화에서 관련 키워드가 반복되면 가산점
        recent_keywords = []
        for turn in state.conversation_history[-3:]:
            recent_keywords.extend(turn.keywords)
        
        recent_overlap = benefit_keywords & set(recent_keywords)
        if len(recent_overlap) >= 2:
            score += 10
    
    return min(score, 100)  # 최대 100점


def rank_benefits_by_score(
    benefits: List[Dict[str, str]],
    state: SessionState,
) -> List[Dict[str, any]]:
    """혜택 리스트를 점수순으로 정렬하고 점수 추가"""
    scored_benefits = []
    
    for benefit in benefits:
        benefit_name = benefit.get("card", "")
        score = calculate_eligibility_score(benefit_name, state)
        
        benefit_with_score = benefit.copy()
        benefit_with_score["eligibility_score"] = score
        scored_benefits.append(benefit_with_score)
    
    # 점수 내림차순 정렬
    scored_benefits.sort(key=lambda x: x["eligibility_score"], reverse=True)
    
    return scored_benefits


def update_user_profile_from_keywords(state: SessionState) -> None:
    """키워드에서 사용자 프로파일 추론"""
    keywords = set(state.user_keywords)
    
    # 연령대 추론
    if any(kw in keywords for kw in ["노인", "어르신", "연금"]):
        state.user_profile.age_range = "60대 이상"
    elif any(kw in keywords for kw in ["청년", "대학", "취업"]):
        state.user_profile.age_range = "20~30대"
    elif any(kw in keywords for kw in ["육아", "아이", "어린이집"]):
        state.user_profile.age_range = "30~40대"
    
    # 고용 상태 추론
    if any(kw in keywords for kw in ["실직", "해고", "구직"]):
        state.user_profile.employment_status = "실업"
    elif any(kw in keywords for kw in ["알바", "아르바이트"]):
        state.user_profile.employment_status = "비정규직"
    
    # 주요 관심사 추론
    if any(kw in keywords for kw in ["월세", "전세", "집"]):
        state.user_profile.primary_concern = "주거"
    elif any(kw in keywords for kw in ["병원", "의료", "건강"]):
        state.user_profile.primary_concern = "의료"
    elif any(kw in keywords for kw in ["생활비", "생계"]):
        state.user_profile.primary_concern = "생계"
    elif any(kw in keywords for kw in ["취업", "일자리"]):
        state.user_profile.primary_concern = "고용"


def get_profile_summary(state: SessionState) -> str:
    """사용자 프로파일 요약 텍스트"""
    profile = state.user_profile
    parts = []
    
    if profile.age_range:
        parts.append(f"연령대: {profile.age_range}")
    if profile.employment_status:
        parts.append(f"고용: {profile.employment_status}")
    if profile.primary_concern:
        parts.append(f"주요 관심: {profile.primary_concern}")
    
    if parts:
        return " | ".join(parts)
    return "프로파일 정보 수집 중"

