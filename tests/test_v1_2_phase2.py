"""
v1.2 Phase 2 테스트 (3-Level Layering)
Assert-based tests (no snapshots)
"""
from __future__ import annotations

import pytest

from state import SessionState, SESSION_STORE
from tools.orchestrator import orchestrate_full_response
from tools.cards import rank_support_cards, _classify_card_level


def test_normal_case_includes_l1_and_l2():
    """
    Phase 2 테스트: 일반 케이스 → L1 + L2 (선택적 L3) 포함, 카드 개수 2~3개
    """
    state = SessionState()
    state.chosen_domain = "주거·월세"
    state.user_keywords = ["월세", "30대", "서울"]  # USER_STATED 충분
    
    user_message = "30대이고 서울에 살아요. 월세 지원 받을 수 있나요?"
    result = orchestrate_full_response(user_message, state, skip_onboarding=True)
    
    # mcp_meta.layering 확인
    assert "mcp_meta" in result
    mcp_meta = result["mcp_meta"]
    assert "layering" in mcp_meta
    layering = mcp_meta["layering"]
    
    assert layering.get("applied") is True
    assert layering.get("l1_count", 0) >= 1  # L1 최소 1개
    assert layering.get("l2_count", 0) >= 1  # L2 최소 1개
    
    # 카드 개수 2~3개
    cards = result.get("step_3_benefit_cards", {}).get("cards", [])
    assert 2 <= len(cards) <= 3
    
    # L1 카드에 "[조건부]" prefix 확인
    l1_cards = [card for card in cards if "[조건부]" in card.get("card", "")]
    assert len(l1_cards) >= 1
    
    # L2 카드에 "[누구나]" prefix 확인
    l2_cards = [card for card in cards if "[누구나]" in card.get("card", "")]
    assert len(l2_cards) >= 1
    
    # L2/L3 카드에 action_steps 없음 확인
    # (action_steps는 L1이 있을 때만 생성되므로, L2/L3만 있으면 None)
    if len(l1_cards) == 0:
        assert result.get("step_4_action_steps", {}).get("actions") is None


def test_unclear_context_allows_l2_and_l3_only():
    """
    Phase 2 테스트: 맥락 불명확 → L2 + L3만 허용, 카드 개수 2~3개
    """
    state = SessionState()
    state.chosen_domain = "주거·월세"
    state.user_keywords = []  # USER_STATED 부족 (맥락 불명확)
    
    user_message = "도움이 필요해요"  # 맥락 불명확
    result = orchestrate_full_response(user_message, state, skip_onboarding=True)
    
    # mcp_meta.layering 확인
    assert "mcp_meta" in result
    mcp_meta = result["mcp_meta"]
    layering = mcp_meta.get("layering", {})
    
    # L1이 없거나 매우 적음
    assert layering.get("l1_count", 0) == 0 or layering.get("l1_count", 0) < layering.get("l2_count", 0)
    
    # L2, L3는 있어야 함
    assert layering.get("l2_count", 0) >= 1
    assert layering.get("l3_count", 0) >= 1
    
    # 카드 개수 2~3개
    cards = result.get("step_3_benefit_cards", {}).get("cards", [])
    assert 2 <= len(cards) <= 3
    
    # L1 카드가 없거나 매우 적음
    l1_cards = [card for card in cards if "[조건부]" in card.get("card", "")]
    assert len(l1_cards) == 0 or len(l1_cards) < len([c for c in cards if "[누구나]" in c.get("card", "")])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

