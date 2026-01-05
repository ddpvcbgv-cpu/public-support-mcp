"""
v0.50 엔진 응답 구조 ①~⑦ 자동 실행 오케스트레이터
"""
from __future__ import annotations

from typing import Dict, Any, Optional

from state import SessionState
from constants import REQUIRED_PHRASES, ONBOARDING_MESSAGE

from tools.normalize import normalize_user_context
from tools.urgency import assess_urgency_level
from tools.domains import expose_available_domains, DOMAIN_HINTS
from tools.cards import rank_support_cards
from tools.actions import generate_action_steps
from tools.fallback import generate_fallback_paths
from tools.safety import compose_safe_response
from tools.region import collect_region_context
from tools.policy_trigger import reveal_policy_name_if_triggered
from tools.followup import suggest_followup_options


def _should_unlock_domain(user_message: str, state: SessionState) -> bool:
    """
    ChatGPT 전용: domain_lock을 해제해야 하는지 판단
    
    Returns:
        True: unlock (orchestrate 허용)
        False: lock 유지 (rank_support_cards 사용 권장)
    """
    message_lower = user_message.lower()
    current_domain = state.chosen_domain
    
    if not current_domain:
        return True  # lock이 없으면 항상 허용
    
    # 1. 명시적 전환 요청 감지
    unlock_keywords = [
        "다른 분야", "다른 지원", "추가로", "또 다른",
        "다른 것", "다른 건", "다른 거", "다른 게",
        "이것도", "이것도 궁금", "이것도 알고 싶",
        "전환", "바꾸고 싶", "변경"
    ]
    if any(kw in message_lower for kw in unlock_keywords):
        return True
    
    # 2. 새로운 도메인 키워드 감지
    # 현재 도메인의 키워드 제외
    current_hints = DOMAIN_HINTS.get(current_domain, [])
    message_without_current = message_lower
    for hint in current_hints:
        message_without_current = message_without_current.replace(hint, "")
    
    # 다른 도메인 키워드가 있는지 확인
    other_domain_detected = False
    for domain, hints in DOMAIN_HINTS.items():
        if domain != current_domain:
            if any(hint in message_without_current for hint in hints):
                other_domain_detected = True
                break
    
    # 3. 새로운 상황 설명 (완전히 다른 맥락)
    # ⚠️ 보완: "그런데", "그리고", "또한" 단독으로는 unlock하지 않음
    new_situation_keywords = [
        "이제", "이번엔", "이번에는",
        "새로운", "다른 문제", "다른 상황"
    ]
    
    # "그런데", "그리고", "또한"은 다른 도메인 키워드와 함께 있을 때만 unlock
    weak_connectors = ["그런데", "그리고", "또한"]
    has_weak_connector = any(kw in message_lower for kw in weak_connectors)
    
    if has_weak_connector:
        # 다른 도메인 키워드와 함께 있으면 unlock
        if other_domain_detected:
            return True
        # 단독으로는 unlock하지 않음 (같은 도메인 심화로 간주)
        return False
    
    # 강한 새로운 상황 키워드 + 도메인 키워드
    if any(kw in message_lower for kw in new_situation_keywords):
        if other_domain_detected:
            return True
    
    return False


def _is_emotion_only(user_message: str, state: SessionState) -> bool:
    """
    ChatGPT 전용: 감정 발화만 있는지 판단 (상태 변경 없음)
    
    ⚠️ 보완: 질문형 어미가 있으면 요청으로 간주
    
    Returns:
        True: 감정 표현만 (상태 유지)
        False: 구체적 요청 포함 (새로운 요청)
    """
    message_lower = user_message.lower()
    
    # 감정 키워드
    emotion_keywords = [
        "힘들어", "힘들다", "힘듦", "힘들",
        "무서워", "무섭", "불안해", "불안",
        "걱정돼", "걱정", "두려워", "두려움",
        "슬퍼", "슬프", "우울해", "우울",
        "답답해", "답답", "막막해", "막막",
        "너무", "정말", "진짜", "완전히"
    ]
    
    # 구체적 요청 키워드
    request_keywords = [
        "필요", "받고 싶", "알고 싶", "궁금",
        "도움", "지원", "알려줘", "말해줘",
        "방법", "어떻게", "무엇", "뭐가",
        "신청", "연결", "상담", "문의"
    ]
    
    # 도메인 키워드
    has_domain_keyword = False
    for hints in DOMAIN_HINTS.values():
        if any(hint in message_lower for hint in hints):
            has_domain_keyword = True
            break
    
    has_emotion = any(kw in message_lower for kw in emotion_keywords)
    has_request = any(kw in message_lower for kw in request_keywords)
    
    # 🆕 보완: 감정 + 질문형 어미는 요청으로 간주
    question_markers = ["어떻게", "뭐", "뭘", "할 수", "해야", "해야 할지", "해야 할까"]
    has_question = any(q in message_lower for q in question_markers)
    
    if has_emotion and has_question:
        # "막막해요... 어떻게 해야 할지 모르겠어요" → 요청으로 간주
        return False
    
    # 감정만 있고 요청/도메인/질문 키워드가 없으면 감정 발화로 판단
    if has_emotion and not has_request and not has_domain_keyword and not has_question:
        return True
    
    return False


def _should_allow_reorchestrate(user_message: str, state: SessionState) -> bool:
    """
    ChatGPT 전용: orchestrate 재호출을 허용해야 하는지 판단
    
    Returns:
        True: 재호출 허용
        False: 재호출 금지 (rank_support_cards 등 다른 도구 사용)
    """
    # 1. 첫 호출은 항상 허용
    if state.interaction_count == 0:
        return True
    
    # 2. domain_lock이 없으면 허용
    if not state.chosen_domain:
        return True
    
    # 3. unlock 조건 충족 시 허용
    if _should_unlock_domain(user_message, state):
        return True
    
    # 4. 감정 발화만 있으면 상태 유지 (재호출 불필요)
    if _is_emotion_only(user_message, state):
        return False
    
    # 5. 그 외에는 재호출 금지 (rank_support_cards 사용)
    return False


def orchestrate_full_response(
    user_message: str,
    state: SessionState,
    skip_onboarding: bool = False,
    client_type: str = "default"
) -> Dict[str, Any]:
    """
    v0.50 엔진 스펙에 따라 ①~⑦ 단계를 자동으로 실행합니다.
    
    Args:
        user_message: 사용자 입력 메시지
        state: 세션 상태
        skip_onboarding: True면 Onboarding 메시지 생략
        client_type: 클라이언트 타입 ("playmcp" | "chatgpt" | "default")
    
    Returns:
        전체 응답 구조 (①~⑦ 단계 포함)
    """
    response = {}
    
    # 🆕 ChatGPT 전용: domain_lock 및 orchestrate 1회성 제한
    if client_type == "chatgpt":
        # 1. orchestrate 재호출 허용 여부 체크
        if not _should_allow_reorchestrate(user_message, state):
            # 재호출 금지: rank_support_cards 사용 권장 메시지 반환
            current_domain = state.chosen_domain or "현재 선택한 분야"
            
            # 🆕 보완: UX 개선된 메시지 (톤 조정)
            response["_redirect_to_rank_cards"] = {
                "message": (
                    f"이미 {current_domain} 쪽으로 이야기를 나누고 있어서, "
                    f"이제는 해당 지원을 더 자세히 보는 게 좋아 보여요. "
                    f"'rank_support_cards' 도구를 사용해주세요."
                ),
                "domain": state.chosen_domain
            }
            return response
        
        # 2. 감정 발화만 있는 경우 상태 유지 (기존 응답 유지)
        if _is_emotion_only(user_message, state) and state.interaction_count > 0:
            # 기존 상태 유지 메시지 반환
            response["_emotion_only"] = {
                "message": (
                    "감정을 표현해주셔서 감사합니다. "
                    "구체적인 지원이 필요하시면 어떤 분야인지 말씀해주세요."
                ),
                "maintain_state": True
            }
            return response
    
    # 🆕 PlayMCP 전용: 사용자 메시지 분석하여 충분한 정보가 있으면 onboarding 자동 스킵
    if state.interaction_count == 0 and not skip_onboarding and client_type == "playmcp":
        # 구체적인 정보 키워드 확인
        info_keywords = ["나이", "살", "세", "소득", "월세", "전세", "주거", "가족", 
                        "부모", "혼자", "싱글", "학생", "고등학생", "대학생",
                        "지원", "도움", "필요", "받을 수", "궁금", "알려주세요"]
        
        # 명확한 요청 키워드 확인
        request_keywords = ["받을 수 있나요", "도움이 필요해요", "알려주세요", 
                           "방법", "어떻게", "무엇", "뭐가", "궁금"]
        
        message_lower = user_message.lower()
        has_info = any(kw in message_lower for kw in info_keywords)
        has_request = any(kw in message_lower for kw in request_keywords)
        
        # 충분한 정보가 있거나 명확한 요청이 있으면 onboarding 스킵
        if has_info and has_request:
            skip_onboarding = True
    
    # 🔹 Onboarding (최초 1회만, 스킵 조건 확인 후)
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
            lines.append(f"지금 상황을 기준으로 보면, {domain} 분야에서 열려 있는 선택지입니다.")
            lines.append("")
            
            for i, card in enumerate(cards, 1):
                card_title = card.get('card', '')
                lines.append(f"【{card_title}】")
                lines.append("")
                
                # 🆕 v1.1.1: Evidence Line 추가
                if card.get('이게_뭐냐면'):
                    description = card.get('이게_뭐냐면', '').rstrip()
                    evidence_line = " 근거: 공식 안내 참조 · 공공 지원 안내 (검증 2025-12)"
                    lines.append(f"이게 뭐냐면:")
                    lines.append(description + evidence_line)
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

