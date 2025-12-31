"""
v0.50 엔진 응답 구조 ①~⑦ 자동 실행 오케스트레이터
v1.2: mcp_meta 추가 (Phase 1)
"""
from __future__ import annotations

from typing import Dict, Any, Optional, List
from uuid import uuid4

from schemas import MCPMeta
from state import SessionState
from constants import REQUIRED_PHRASES, ONBOARDING_MESSAGE

from tools.normalize import normalize_user_context
from tools.urgency import assess_urgency_level
from tools.domains import expose_available_domains, DOMAIN_HINTS
from tools.cards import rank_support_cards
from tools.actions import generate_action_steps
from tools.fallback import generate_fallback_paths
from tools.safety import compose_safe_response, detect_crisis_intent, generate_crisis_step1_question, generate_crisis_step2_message
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


def _check_legal_domain(user_message: str, state: SessionState) -> bool:
    """
    Phase 2 ADD-6: Legal-ready guard
    법적 이슈 유사 도메인 감지
    """
    legal_keywords = ["법률", "법적", "소송", "변호사", "법원", "재판", "고소", "고발", "위법", "불법"]
    user_message_lower = user_message.lower()
    return any(kw in user_message_lower for kw in legal_keywords)


def _build_selection_rationale(user_message: str, state: SessionState, normalize_result: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    v1.2 B 요구사항: selection_rationale 생성
    USER_STATED vs INFERRED 구분
    """
    rationale = []
    keywords = normalize_result.get("keywords", [])
    known_facts = state.known_facts
    
    # 명시적으로 언급된 정보 (USER_STATED)
    user_stated_keys = {
        "나이": ["나이", "살", "세", "20대", "30대", "40대", "50대", "60대"],
        "소득": ["소득", "월급", "월소득", "알바", "아르바이트"],
        "주거": ["월세", "전세", "보증금", "집"],
        "가구형태": ["혼자", "1인", "가족", "부모", "아이", "자녀"],
        "지역": ["서울", "부산", "경기", "인천", "대구", "광주", "대전", "울산"],
    }
    
    message_lower = user_message.lower()
    
    for key, patterns in user_stated_keys.items():
        if any(pattern in message_lower for pattern in patterns):
            # 사용자가 명시적으로 언급
            value = next((p for p in patterns if p in message_lower), patterns[0])
            rationale.append({
                "key": key,
                "value": value,
                "source": "USER_STATED"
            })
    
    # 추론된 정보 (INFERRED) - known_facts에 있지만 명시적으로 언급되지 않은 것
    for key, value in known_facts.items():
        if key not in [r["key"] for r in rationale]:
            # 추론된 정보
            rationale.append({
                "key": key,
                "value": str(value),
                "source": "INFERRED"
            })
    
    return rationale


def _calculate_confidence(rationale: List[Dict[str, str]]) -> tuple[str, bool]:
    """
    v1.2 C 요구사항: confidence 및 needs_verification 계산
    """
    # USER_STATED distinct key count
    user_stated_keys = set()
    has_inferred = False
    
    for item in rationale:
        if item.get("source") == "USER_STATED":
            user_stated_keys.add(item.get("key"))
        elif item.get("source") == "INFERRED":
            has_inferred = True
    
    user_stated_count = len(user_stated_keys)
    
    # confidence 계산
    if user_stated_count >= 3:
        confidence = "high"
    elif user_stated_count >= 1:
        confidence = "med"
    else:
        confidence = "low"
    
    # needs_verification: INFERRED 존재 시 항상 True
    needs_verification = has_inferred
    
    return confidence, needs_verification


def _build_mcp_meta(
    user_message: str,
    state: SessionState,
    normalize_result: Dict[str, Any],
    cards_result: Dict[str, Any],
    request_id: Optional[str] = None,
    error_code: Optional[str] = None
) -> MCPMeta:
    """
    v1.2: mcp_meta 생성
    """
    # selection_rationale 생성
    rationale = _build_selection_rationale(user_message, state, normalize_result)
    
    # confidence, needs_verification 계산
    confidence, needs_verification = _calculate_confidence(rationale)
    
    # INFERRED 감지 시 TEMPORARY_SUGGESTION + action_lock
    has_inferred = any(item.get("source") == "INFERRED" for item in rationale)
    user_stated_keys = set(item.get("key") for item in rationale if item.get("source") == "USER_STATED")
    
    # 여러 L1 카드가 있을 수 있으므로, 각 카드별로 card_overrides 설정
    cards = cards_result.get("cards", [])
    l1_cards = [i for i, card in enumerate(cards) if card.get("_level") == "L1" or "[조건부]" in card.get("card", "")]
    
    # 이전 confirmation이 처리되었으면 unlock 가능
    # (confirmation_processed는 orchestrate_full_response에서 전달 필요)
    # 현재는 함수 내에서 직접 체크 불가하므로, has_inferred 재계산으로 처리
    # confirmation 후에는 INFERRED가 known_facts로 이동하므로 has_inferred가 False가 될 수 있음
    
    card_state = "TEMPORARY_SUGGESTION" if has_inferred else None
    action_lock = has_inferred
    
    # 이전 mcp_meta에서 confirmation이 있었고 처리되었는지 확인
    # (이 함수는 _build_mcp_meta이므로 previous_mcp_meta를 직접 받을 수 없음)
    # 대신 orchestrate_full_response에서 action_lock을 재설정
    
    # card_overrides: 각 L1 카드별 개별 상태 관리 (ADD-1)
    card_overrides = []
    if l1_cards:
        for card_idx in l1_cards:
            # 각 L1 카드에 동일한 상태 적용 (현재는 모두 동일)
            # 나중에 개별 카드별로 다르게 설정 가능
            card_overrides.append({
                "card_id_or_index": card_idx,
                "card_state": card_state,
                "action_lock": action_lock
            })
    
    # 확인 질문 생성 (INFERRED가 있을 때만)
    confirmation = None
    if has_inferred:
        inferred_keys = [item["key"] for item in rationale if item.get("source") == "INFERRED"]
        if inferred_keys:
            # 첫 번째 INFERRED 키에 대한 확인 질문
            target_key = inferred_keys[0]
            if target_key == "가구형태":
                confirmation = {
                    "question": "가구 형태를 알려주세요",
                    "options": ["1인가구", "2인가구", "3인 이상"],
                    "expected_values": ["1인가구", "2인가구", "3인 이상"],
                    "target_keys": ["가구형태"]
                }
            elif target_key == "소득":
                confirmation = {
                    "question": "월 소득 수준을 알려주세요",
                    "options": ["100만원 미만", "100-200만원", "200만원 이상"],
                    "expected_values": ["100만원 미만", "100-200만원", "200만원 이상"],
                    "target_keys": ["소득"]
                }
            else:
                # 기본 확인 질문
                confirmation = {
                    "question": f"{target_key} 정보를 확인해주세요",
                    "options": ["예", "아니오"],
                    "expected_values": ["예", "아니오"],
                    "target_keys": [target_key]
                }
    
    # card_state가 TEMPORARY_SUGGESTION이면 confidence는 high가 될 수 없음
    if card_state == "TEMPORARY_SUGGESTION" and confidence == "high":
        confidence = "med"
    
    return MCPMeta(
        selection_rationale=rationale,
        card_state=card_state,
        action_lock=action_lock,
        confirmation=confirmation,
        card_overrides=card_overrides,  # ADD-1: 카드별 오버라이드
        confidence=confidence,
        needs_verification=needs_verification,
        safety_status=None,
        error_code=error_code,
        request_id=request_id,
        retry_after=None,
    )


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
    client_type: str = "default",
    request_id: Optional[str] = None,
    previous_mcp_meta: Optional[Dict[str, Any]] = None
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
    
    # v1.2 E: Crisis 2-step guardrail (가장 먼저 체크)
    crisis_info = detect_crisis_intent(user_message)
    if crisis_info:
        # Step 1: 안전 확인 질문
        # 이전 응답에서 safety_status를 확인 (이미 Step 1을 했는지)
        previous_safety_status = getattr(state, '_previous_safety_status', None)
        
        if previous_safety_status == "UNSAFE":
            # Step 2: UNSAFE 확인 시 plain text 메시지 반환 (카드 없음)
            crisis_message = generate_crisis_step2_message(crisis_info, "UNSAFE")
            mcp_meta = MCPMeta(
                selection_rationale=[],
                safety_status="UNSAFE",
                error_code="SAFETY_GUARDRAIL_TRIGGERED",
                layering={"l1_count": 0, "l2_count": 0, "l3_count": 0, "applied": False},  # Phase 2: 레이어링 우회
                card_layers=[],
            )
            response["crisis_step2"] = {
                "message": crisis_message,
                "crisis_type": crisis_info.get("crisis_type")
            }
            response["mcp_meta"] = mcp_meta.model_dump()
            # 카드 없이 반환 (레이어링 우회)
            return response
        elif previous_safety_status is None:
            # Step 1: 안전 확인 질문
            step1_question = generate_crisis_step1_question(crisis_info)
            mcp_meta = MCPMeta(
                selection_rationale=[],
                safety_status=None,  # 아직 확인 전
                error_code="SAFETY_GUARDRAIL_TRIGGERED",
                layering={"l1_count": 0, "l2_count": 0, "l3_count": 0, "applied": False},  # Phase 2
                card_layers=[],
            )
            response["crisis_step1"] = {
                "question": step1_question["question"],
                "options": step1_question["options"],
                "expected_values": step1_question["expected_values"],
                "crisis_type": crisis_info.get("crisis_type")
            }
            response["mcp_meta"] = mcp_meta.model_dump()
            # 사용자가 응답할 때까지 대기
            return response
        # previous_safety_status == "SAFE" or "NOT_SURE"이면 일반 플로우로 진행
    
    # v1.2: Confirmation 응답 처리 및 unlock 체크
    from tools.confirmation import process_confirmation_response, check_should_unlock_actions
    
    confirmation_processed = False
    if previous_mcp_meta:
        confirmation = previous_mcp_meta.get("confirmation")
        if confirmation:
            confirmation_result = process_confirmation_response(
                user_message, state, confirmation
            )
            if confirmation_result.get("processed"):
                confirmation_processed = True
    
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
    
    # Phase 2 ADD-6: Legal-ready guard 체크
    is_legal_domain = _check_legal_domain(user_message, state)
    
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
    
    # Phase 2: 맥락 불명확 체크 (L2+L3만 허용)
    # USER_STATED가 적고 INFERRED가 많으면 맥락 불명확
    user_stated_keywords = ["나이", "살", "세", "소득", "월세", "전세", "주거", "가족", "부모", "혼자", "싱글"]
    user_stated_count = len([kw for kw in state.user_keywords if kw in user_stated_keywords])
    is_context_unclear = user_stated_count < 2
    
    # 맥락 불명확 시 L1 제거 (L2+L3만)
    if is_context_unclear:
        cards_result["cards"] = [
            card for card in cards_result.get("cards", [])
            if card.get("_level") in ["L2", "L3"] or "[누구나]" in card.get("card", "") or "[공식경로]" in card.get("card", "")
        ]
    
    response["step_3_benefit_cards"] = cards_result
    
    # v1.2: mcp_meta 생성
    # request_id는 함수 파라미터에서 가져옴 (없으면 None)
    mcp_meta = _build_mcp_meta(user_message, state, normalize_result, cards_result, request_id=request_id)
    
    # Confirmation 처리 후 unlock 체크
    if confirmation_processed:
        # confirmation이 처리되었고 모든 target_keys가 업데이트되었으면 unlock
        should_unlock = check_should_unlock_actions(state, previous_mcp_meta)
        if should_unlock:
            mcp_meta.action_lock = False
            mcp_meta.card_state = None  # TEMPORARY_SUGGESTION 해제
            # card_overrides도 업데이트
            for override in mcp_meta.card_overrides:
                override["action_lock"] = False
                override["card_state"] = None
    
    # Phase 2: mcp_meta.layering 추가
    cards = cards_result.get("cards", [])
    l1_count = sum(1 for card in cards if card.get("_level") == "L1" or "[조건부]" in card.get("card", ""))
    l2_count = sum(1 for card in cards if card.get("_level") == "L2" or "[누구나]" in card.get("card", ""))
    l3_count = sum(1 for card in cards if card.get("_level") == "L3" or "[공식경로]" in card.get("card", ""))
    
    mcp_meta.layering = {
        "l1_count": l1_count,
        "l2_count": l2_count,
        "l3_count": l3_count,
        "applied": True
    }
    
    # Phase 2: mcp_meta.card_layers 추가 (embedded_in_card_index 포함)
    card_layers = []
    l2_embedded = cards_result.get("_l2_embedded", False)
    last_l1_index = cards_result.get("_last_l1_index")
    
    for i, card in enumerate(cards):
        level = card.get("_level", "L1")
        layer_info = {
            "card_id_or_index": i,
            "level": level,
        }
        # L2가 L1에 embedded된 경우 (L1=3일 때 마지막 L1에 L2 포함)
        # 마지막 L1 카드에 embedded_in_card_index 정보 추가
        if level == "L1" and l2_embedded and last_l1_index is not None and i == last_l1_index:
            # 이 L1 카드에 L2가 embedded되어 있음을 표시
            # (L2 자체는 cards 리스트에 없으므로 별도 레이어 엔트리 불필요)
            pass  # L1 카드 자체에 embedded 정보는 필요 없음 (L2는 별도 카드가 아니므로)
        card_layers.append(layer_info)
    
    # L2가 embedded된 경우, card_layers에 L2 엔트리를 추가하지 않음
    # (L2는 마지막 L1 카드의 일부로만 존재)
    
    mcp_meta.card_layers = card_layers
    
    # Phase 2 ADD-6: Legal 도메인이면 L1은 USER_STATED 충분하고 INFERRED 없을 때만 unlock
    if is_legal_domain:
        # 법적 도메인: L1은 더 보수적으로 처리
        # USER_STATED가 충분하지 않으면 L1을 제거하고 L2+L3만 제공
        rationale = mcp_meta.selection_rationale
        user_stated_keys = set(item.get("key") for item in rationale if item.get("source") == "USER_STATED")
        has_inferred = any(item.get("source") == "INFERRED" for item in rationale)
        
        if len(user_stated_keys) < 2 or has_inferred:
            # L1 제거, L2+L3만 유지
            cards = [card for card in cards if card.get("_level") not in ["L1", None] or "[조건부]" not in card.get("card", "")]
            cards_result["cards"] = cards
            l1_count = 0
            mcp_meta.layering["l1_count"] = 0
            mcp_meta.action_lock = True  # L1이 없으므로 action_steps도 생성 안 함
            # card_layers도 업데이트
            mcp_meta.card_layers = [
                {
                    "card_id_or_index": i,
                    "level": card.get("_level", "L2"),
                }
                for i, card in enumerate(cards)
            ]
    
    # Phase 2: L3 포함 조건 추가 체크 (ADD-5) - mcp_meta 생성 후
    # (any L1 action_lock==true) OR (any card stale==true) OR
    # (user asks verify/apply/how/where) OR
    # (mcp_meta.error_code in {RATE_LIMITED, UPSTREAM_TIMEOUT, UPSTREAM_QUOTA_EXCEEDED})
    l3_should_include = False
    user_message_lower = user_message.lower()
    verify_keywords = ["확인", "신청", "어떻게", "어디로", "방법", "절차", "문의", "어디서"]
    
    if mcp_meta.action_lock:
        l3_should_include = True
    elif any(card.get("stale") for card in cards):
        l3_should_include = True
    elif any(kw in user_message_lower for kw in verify_keywords):
        l3_should_include = True
    elif mcp_meta.error_code in ["RATE_LIMITED", "UPSTREAM_TIMEOUT", "UPSTREAM_QUOTA_EXCEEDED"]:
        l3_should_include = True
    
    if l3_should_include and l3_count == 0:
        from tools.cards import _create_l3_card, _get_card_metadata
        l3_card = _create_l3_card(cards_result.get("domain", ""), state)
        l3_card_with_meta = _get_card_metadata(cards_result.get("domain", ""), l3_card)
        l3_card_with_meta["card"] = f"[공식경로] {l3_card_with_meta.get('card', '공식 확인 경로')}"
        l3_card_with_meta["_level"] = "L3"
        cards_result["cards"].append(l3_card_with_meta)
        l3_count += 1
        mcp_meta.layering["l3_count"] = l3_count
        mcp_meta.card_layers.append({"card_id_or_index": len(cards), "level": "L3"})
        # cards 변수도 업데이트
        cards = cards_result.get("cards", [])
    
    # 🔹 ④ 지금 바로 할 수 있는 행동 (1~3단계)
    # v1.2: action_lock이 True면 action_steps를 생성하지 않음
    # Phase 2: L1 카드에만 action_steps 적용 (L2/L3는 제거)
    actions_result = None
    fallback_result = None
    
    if not mcp_meta.action_lock:
        # L1 카드가 있는 경우에만 action_steps 생성
        has_l1 = any(
            card.get("_level") == "L1" or "[조건부]" in card.get("card", "")
            for card in cards_result.get("cards", [])
        )
        if has_l1:
            actions_result = generate_action_steps(state)
            fallback_result = generate_fallback_paths(state)
    
    response["step_4_action_steps"] = {
        "actions": actions_result,
        "fallback": fallback_result,
    }
    
    # Phase 2: L2/L3 카드에서 action_steps/CTA 제거 확인
    # (이미 L1 카드가 있을 때만 action_steps 생성하도록 위에서 처리)
    
    # v1.2: mcp_meta를 response에 추가 (UI 노출 안 함)
    response["mcp_meta"] = mcp_meta.model_dump()
    
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
    
    # v1.2: 이전 mcp_meta 저장 (다음 요청에서 confirmation 처리용)
    state.previous_mcp_meta = mcp_meta.model_dump()
    
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
                
                # v1.2 A: Evidence line 추가
                if card.get('evidence'):
                    lines.append(card.get('evidence'))
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

