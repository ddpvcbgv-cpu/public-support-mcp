"""
v1.2: Confirmation 응답 처리 및 unlock 로직
"""
from __future__ import annotations

from typing import Dict, Any, Optional

from state import SessionState


def process_confirmation_response(
    user_message: str,
    state: SessionState,
    previous_confirmation: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    사용자의 confirmation 응답을 처리하고 context를 업데이트
    
    Args:
        user_message: 사용자 응답 메시지
        state: 세션 상태
        previous_confirmation: 이전에 제공된 confirmation 정보
    
    Returns:
        {
            "processed": bool,  # 처리 성공 여부
            "updated_keys": List[str],  # 업데이트된 키 목록
            "should_unlock": bool  # action_lock 해제 여부
        }
    """
    if not previous_confirmation:
        return {"processed": False, "updated_keys": [], "should_unlock": False}
    
    target_keys = previous_confirmation.get("target_keys", [])
    expected_values = previous_confirmation.get("expected_values", [])
    options = previous_confirmation.get("options", [])
    
    if not target_keys:
        return {"processed": False, "updated_keys": [], "should_unlock": False}
    
    # 사용자 메시지에서 선택값 추출
    user_message_lower = user_message.lower()
    selected_value = None
    
    # 옵션 중 하나와 일치하는지 확인
    for option in options:
        if option.lower() in user_message_lower or user_message_lower in option.lower():
            selected_value = option
            break
    
    # expected_values와도 비교
    if not selected_value:
        for expected in expected_values:
            if expected.lower() in user_message_lower or user_message_lower in expected.lower():
                selected_value = expected
                break
    
    if not selected_value:
        # 명시적 선택이 없으면 처리 실패
        return {"processed": False, "updated_keys": [], "should_unlock": False}
    
    # state.known_facts 업데이트
    updated_keys = []
    for target_key in target_keys:
        # target_key에 맞게 값 변환
        if target_key == "가구형태":
            # "1인가구", "2인가구", "3인 이상" -> known_facts에 저장
            state.known_facts[target_key] = selected_value
        elif target_key == "소득":
            # 소득 수준 저장
            state.known_facts[target_key] = selected_value
        else:
            # 기본: 선택값 그대로 저장
            state.known_facts[target_key] = selected_value
        
        updated_keys.append(target_key)
    
    # 모든 target_keys가 업데이트되었으면 unlock
    should_unlock = len(updated_keys) == len(target_keys)
    
    return {
        "processed": True,
        "updated_keys": updated_keys,
        "should_unlock": should_unlock
    }


def check_should_unlock_actions(
    state: SessionState,
    previous_mcp_meta: Optional[Dict[str, Any]]
) -> bool:
    """
    이전 confirmation이 처리되었는지 확인하고 unlock 여부 판단
    
    Args:
        state: 세션 상태
        previous_mcp_meta: 이전 응답의 mcp_meta
    
    Returns:
        action_lock 해제 여부
    """
    if not previous_mcp_meta:
        return False
    
    confirmation = previous_mcp_meta.get("confirmation")
    if not confirmation:
        return False
    
    target_keys = confirmation.get("target_keys", [])
    if not target_keys:
        return False
    
    # 모든 target_keys가 known_facts에 있는지 확인
    for target_key in target_keys:
        if target_key not in state.known_facts:
            return False
    
    return True

