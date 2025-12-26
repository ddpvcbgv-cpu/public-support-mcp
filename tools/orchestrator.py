"""
v0.50 엔진 응답 구조 ①~⑦ 자동 실행 오케스트레이터
"""
from __future__ import annotations

from typing import Dict, Any, Optional

from state import SessionState
from constants import REQUIRED_PHRASES, ONBOARDING_MESSAGE

from tools.normalize import normalize_user_context
from tools.urgency import assess_urgency_level
from tools.domains import expose_available_domains
from tools.cards import rank_support_cards
from tools.actions import generate_action_steps
from tools.fallback import generate_fallback_paths
from tools.safety import compose_safe_response
from tools.region import collect_region_context
from tools.policy_trigger import reveal_policy_name_if_triggered
from tools.followup import suggest_followup_options


def orchestrate_full_response(
    user_message: str,
    state: SessionState,
    skip_onboarding: bool = False
) -> Dict[str, Any]:
    """
    v0.50 엔진 스펙에 따라 ①~⑦ 단계를 자동으로 실행합니다.
    
    Args:
        user_message: 사용자 입력 메시지
        state: 세션 상태
        skip_onboarding: True면 Onboarding 메시지 생략
    
    Returns:
        전체 응답 구조 (①~⑦ 단계 포함)
    """
    response = {}
    
    # 🔹 Onboarding (최초 1회만)
    if state.interaction_count == 0 and not skip_onboarding:
        response["onboarding"] = ONBOARDING_MESSAGE
        # Onboarding 후에는 사용자가 입력할 때까지 대기
        state.interaction_count += 1
        return response
    
    # 🔹 ① 지금 상황 요약 (판단 없이)
    normalize_result = normalize_user_context(user_message, state)
    response["step_1_situation_summary"] = {
        "intro": REQUIRED_PHRASES["situation_intro"],
        "summary": normalize_result.get("summary", ""),
        "keywords": normalize_result.get("keywords", []),
    }
    
    # 🔹 긴급도 평가 (내부 계산용)
    urgency_context = {"message": user_message}
    urgency_result = assess_urgency_level(urgency_context, state)
    
    # 🔹 ② 지금 상황에서 열려 있는 지원 '분야' 안내
    domains_result = expose_available_domains(state)
    domains = domains_result.get("domains", [])
    
    # 스마트 기본값 제안 (분야가 3개 이상일 때)
    smart_default_message = None
    if len(domains) >= 3:
        top_3 = " / ".join(domains[:3])
        smart_default_message = REQUIRED_PHRASES["smart_default"].format(domains=top_3)
    
    response["step_2_available_domains"] = {
        "intro": REQUIRED_PHRASES["domain_intro"],
        "domains": domains,
        "smart_default": smart_default_message,
    }
    
    # 🔹 ③ 지금 단계에서 먼저 열어볼 '혜택 카드' (TOP 2~3)
    cards_result = rank_support_cards(state)
    response["step_3_benefit_cards"] = cards_result
    
    # 🔹 ④ 지금 바로 할 수 있는 행동 (1~3단계)
    actions_result = generate_action_steps(state)
    fallback_result = generate_fallback_paths(state)
    
    response["step_4_action_steps"] = {
        "actions": actions_result,
        "fallback": fallback_result,
    }
    
    # 🔹 지역 정보 수집 (필요 시)
    if not state.region_hint:
        region_result = collect_region_context(state)
        response["region_collection"] = region_result
    
    # 🔹 ⑤ 제도명 공개 트리거 규칙
    policy_trigger_result = reveal_policy_name_if_triggered(user_message, state)
    if policy_trigger_result.get("triggered"):
        response["step_5_policy_reveal"] = policy_trigger_result
    
    # 🔹 ⑥ 확장 가능성 안내 (항상 포함)
    followup_result = suggest_followup_options(state)
    response["step_6_expansion"] = followup_result
    
    # 🔹 ⑦ 감정 안전 문장 (맨 마지막)
    safety_message = compose_safe_response(state)
    response["step_7_safety"] = safety_message
    
    # 상호작용 카운트 증가
    state.interaction_count += 1
    
    return response


def format_orchestrated_response(orchestrated: Dict[str, Any]) -> str:
    """
    orchestrate_full_response의 결과를 읽기 쉬운 텍스트로 변환합니다.
    
    Args:
        orchestrated: orchestrate_full_response 반환값
    
    Returns:
        포맷팅된 텍스트 응답
    """
    lines = []
    
    # Onboarding
    if "onboarding" in orchestrated:
        return orchestrated["onboarding"]
    
    # ① 상황 요약
    if "step_1_situation_summary" in orchestrated:
        step1 = orchestrated["step_1_situation_summary"]
        lines.append(f"{step1['intro']}, {step1['summary']}")
        lines.append("")
    
    # ② 분야 안내
    if "step_2_available_domains" in orchestrated:
        step2 = orchestrated["step_2_available_domains"]
        lines.append(step2["intro"])
        lines.append("")
        
        if step2.get("domains"):
            for domain in step2["domains"]:
                lines.append(f"  • {domain}")
            lines.append("")
        
        if step2.get("smart_default"):
            lines.append(step2["smart_default"])
            lines.append("")
    
    # ③ 혜택 카드
    if "step_3_benefit_cards" in orchestrated:
        step3 = orchestrated["step_3_benefit_cards"]
        domain = step3.get("domain", "")
        cards = step3.get("cards", [])
        
        if cards:
            lines.append(f"지금 상황을 기준으로 보면, {domain} 분야에서 열려 있는 선택지를 정리해봤어요.")
            lines.append("")
            
            for i, card in enumerate(cards, 1):
                lines.append(f"【{card.get('card', '')}】")
                lines.append("")
                
                if card.get('이게_뭐냐면'):
                    lines.append(f"이게 뭐냐면:")
                    lines.append(card.get('이게_뭐냐면'))
                    lines.append("")
                
                if card.get('왜_지금_맞냐면'):
                    lines.append(f"왜 지금 맞냐면:")
                    lines.append(card.get('왜_지금_맞냐면'))
                    lines.append("")
                
                if card.get('지금_하실_수_있는_말'):
                    lines.append(f"지금 하실 수 있는 말:")
                    lines.append(f'  → "{card.get("지금_하실_수_있는_말")}"')
                    lines.append("")
                
                if card.get('where'):
                    lines.append(f"어디로:")
                    lines.append(card.get('where'))
                    lines.append("")
                
                if card.get('how'):
                    lines.append(f"방법:")
                    lines.append(card.get('how'))
                    lines.append("")
                
                if card.get('막히면'):
                    lines.append(f"막히면:")
                    lines.append(card.get('막히면'))
                    lines.append("")
                
                lines.append("---")
                lines.append("")
    
    # ④ 행동 단계
    if "step_4_action_steps" in orchestrated:
        step4 = orchestrated["step_4_action_steps"]
        actions = step4.get("actions", {})
        
        if actions:
            lines.append("【지금 바로 할 수 있는 행동】")
            lines.append("")
            
            if actions.get("today"):
                lines.append(f"오늘: {actions['today']}")
                lines.append("")
            
            if actions.get("tomorrow"):
                lines.append(f"내일: {actions['tomorrow']}")
                lines.append("")
            
            if actions.get("stuck"):
                lines.append(f"막히면: {actions['stuck']}")
                lines.append("")
    
    # 지역 수집
    if "region_collection" in orchestrated:
        region = orchestrated["region_collection"]
        if region.get("status") == "requesting":
            lines.append(region["message"])
            lines.append("")
    
    # ⑤ 제도명 공개
    if "step_5_policy_reveal" in orchestrated:
        step5 = orchestrated["step_5_policy_reveal"]
        if step5.get("warning_message"):
            lines.append(step5["warning_message"])
            lines.append("")
        
        if step5.get("policy_info"):
            policy = step5["policy_info"]
            policy_name = policy.get("policy_name", "관련 제도")
            lines.append(REQUIRED_PHRASES["policy_reveal"].format(policy_name=policy_name))
            lines.append("")
    
    # ⑥ 확장 가능성
    if "step_6_expansion" in orchestrated:
        step6 = orchestrated["step_6_expansion"]
        lines.append(step6.get("expansion_message", REQUIRED_PHRASES["expansion"]))
        lines.append("")
        
        recommendations = step6.get("recommendations", [])
        if recommendations:
            lines.append("예를 들면:")
            for rec in recommendations:
                lines.append(f"  • {rec['domain']}: {rec['reason']}")
            lines.append("")
    
    # ⑦ 감정 안전
    if "step_7_safety" in orchestrated:
        lines.append("---")
        lines.append("")
        lines.append(orchestrated["step_7_safety"])
    
    return "\n".join(lines)

