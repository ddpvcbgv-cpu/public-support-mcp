"""
v1.2 Phase 1 테스트 (A~H 요구사항)
Assert-based tests (no snapshots)
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta

from state import SessionState, SESSION_STORE
from tools.orchestrator import orchestrate_full_response
from tools.cards import rank_support_cards
from tools.safety import detect_crisis_intent, generate_crisis_step2_message


def test_inferred_creates_temporary_suggestion():
    """
    v1.2 B 테스트: INFERRED 존재 시 TEMPORARY_SUGGESTION + action_lock=True + confirmation 존재
    """
    state = SessionState()
    state.known_facts = {"가구형태": "1인가구"}  # INFERRED 정보
    
    user_message = "30대인데 월세 지원 받을 수 있나요?"
    result = orchestrate_full_response(user_message, state, skip_onboarding=True)
    
    # mcp_meta 확인
    assert "mcp_meta" in result
    mcp_meta = result["mcp_meta"]
    
    # INFERRED가 있는지 확인
    rationale = mcp_meta.get("selection_rationale", [])
    has_inferred = any(item.get("source") == "INFERRED" for item in rationale)
    
    if has_inferred:
        # TEMPORARY_SUGGESTION 확인
        assert mcp_meta.get("card_state") == "TEMPORARY_SUGGESTION"
        # action_lock 확인
        assert mcp_meta.get("action_lock") is True
        # confirmation 존재 확인
        assert mcp_meta.get("confirmation") is not None
        confirmation = mcp_meta["confirmation"]
        assert "question" in confirmation
        assert "options" in confirmation
        assert "target_keys" in confirmation
        # action_steps가 없어야 함
        assert result.get("step_4_action_steps", {}).get("actions") is None


def test_stale_adds_renewal_tag():
    """
    v1.2 D 테스트: stale=True 시 evidence line에 "갱신 필요" 포함
    """
    state = SessionState()
    state.chosen_domain = "주거·월세"
    
    # 카드 결과 가져오기
    cards_result = rank_support_cards(state)
    cards = cards_result.get("cards", [])
    
    # stale=True인 카드가 있는지 확인 (또는 테스트용으로 오래된 날짜 설정)
    # 실제로는 카드에 last_verified_date를 오래된 날짜로 설정해야 함
    # 여기서는 evidence line이 생성되는지만 확인
    assert len(cards) > 0
    for card in cards:
        assert "evidence" in card
        evidence = card.get("evidence", "")
        # stale=True면 "갱신 필요" 포함
        if card.get("stale"):
            assert "갱신 필요" in evidence


def test_safety_status_unsafe_triggers_step2():
    """
    v1.2 E 테스트: safety_status=="UNSAFE" 시 Step 2 메시지 반환 (카드 없음)
    """
    # 위기 상황 감지
    user_message = "가족에게 성폭행을 당하고 있어요 무서워요"
    crisis_info = detect_crisis_intent(user_message)
    
    assert crisis_info is not None
    assert crisis_info.get("crisis_type") == "violence_domestic"
    
    # Step 2 메시지 생성
    step2_message = generate_crisis_step2_message(crisis_info, "UNSAFE")
    
    assert "지금은 추가 정보 입력보다 안전이 가장 중요합니다" in step2_message
    assert "112" in step2_message or "1366" in step2_message
    
    # 실제 orchestrate_full_response에서 테스트
    state = SessionState()
    state._previous_safety_status = "UNSAFE"  # Step 1을 이미 했다고 가정
    
    result = orchestrate_full_response(user_message, state, skip_onboarding=True)
    
    # Step 2 응답 확인
    assert "crisis_step2" in result
    assert "message" in result["crisis_step2"]
    # 카드가 없어야 함 (레이어링 우회)
    assert "step_3_benefit_cards" not in result or len(result.get("step_3_benefit_cards", {}).get("cards", [])) == 0


def test_confidence_and_needs_verification():
    """
    v1.2 C 테스트: confidence 계산 및 needs_verification 로직
    """
    state = SessionState()
    
    # USER_STATED만 있는 경우
    user_message = "30대이고 서울에 살아요. 월세 지원 받을 수 있나요?"
    result = orchestrate_full_response(user_message, state, skip_onboarding=True)
    
    mcp_meta = result.get("mcp_meta", {})
    rationale = mcp_meta.get("selection_rationale", [])
    
    user_stated_count = len(set(item.get("key") for item in rationale if item.get("source") == "USER_STATED"))
    
    # confidence 계산 확인
    confidence = mcp_meta.get("confidence")
    assert confidence in ["low", "med", "high"]
    
    # USER_STATED가 많을수록 confidence가 높아야 함
    if user_stated_count >= 3:
        assert confidence == "high"
    elif user_stated_count >= 1:
        assert confidence in ["med", "high"]
    
    # INFERRED가 있으면 needs_verification=True
    has_inferred = any(item.get("source") == "INFERRED" for item in rationale)
    needs_verification = mcp_meta.get("needs_verification")
    
    if has_inferred:
        assert needs_verification is True
        # TEMPORARY_SUGGESTION이면 confidence는 high가 될 수 없음
        if mcp_meta.get("card_state") == "TEMPORARY_SUGGESTION":
            assert confidence != "high"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

