"""
지역 컨텍스트 수집 도구
"""
from __future__ import annotations

from typing import Dict, Optional

from state import SessionState
from constants import REGION_COLLECTION_PROMPT, REGION_SKIP_MESSAGE


def collect_region_context(state: SessionState, user_input: Optional[str] = None) -> Dict[str, str]:
    """
    사용자의 지역 정보를 부드럽게 수집합니다.
    
    Args:
        state: 세션 상태
        user_input: 사용자가 제공한 지역 정보 (선택적)
    
    Returns:
        지역 수집 메시지 또는 확인 메시지
    """
    # 이미 지역 정보가 있는 경우
    if state.region_hint:
        return {
            "status": "already_collected",
            "region": state.region_hint,
            "message": f"{state.region_hint} 기준으로 안내해드리겠습니다."
        }
    
    # 사용자가 지역 정보를 제공한 경우
    if user_input and user_input.strip():
        # 간단한 지역명 추출 (시/군/구 단위)
        region = user_input.strip()
        state.region_hint = region
        
        return {
            "status": "collected",
            "region": region,
            "message": f"{region} 기준으로 안내해드리겠습니다. 지역별 지원이 조금 더 구체적으로 확인될 수 있어요."
        }
    
    # 지역 정보 수집 요청
    return {
        "status": "requesting",
        "message": REGION_COLLECTION_PROMPT,
        "skip_message": REGION_SKIP_MESSAGE
    }

