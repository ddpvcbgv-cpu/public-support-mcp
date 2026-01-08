"""
v0.50 엔진 응답 구조 ①~⑦ 자동 실행 오케스트레이터
"""
from __future__ import annotations

from typing import Dict, Any, Optional

from state import ConversationPhase, SessionState
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
from tools.signal import detect_signal


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


def _has_minimum_context(state: SessionState) -> bool:
    """
    정보가 최소한 충분히 모였는지 판단
    - 나이/소득/주거/가족/걱정/건강 중 2개 이상 잡히면 True
    
    Returns:
        True: 정보 충분 (분야 안내 단계로 진행 가능)
        False: 정보 부족 (온보딩 필요)
    """
    if isinstance(state.user_keywords, list):
        text = " ".join(state.user_keywords).lower()
    else:
        text = str(state.user_keywords).lower()

    score = 0

    # 1) 나이·생애주기 정보
    age_keywords = [
        "나이", "살", "세",
        "10대", "20대", "30대", "40대", "50대", "60대", "70대",
        "청년", "중장년", "노인", "어르신", "미성년자",
        "초등학생", "중학생", "고등학생", "대학생",
    ]
    if any(kw in text for kw in age_keywords):
        score += 1

    # 2) 주거 정보
    housing_keywords = [
        "월세", "전세", "반전세", "보증금",
        "주거", "집", "방",
        "고시원", "고시텔", "원룸", "오피스텔", "쉐어하우스", "기숙사",
        "공공임대", "임대주택", "lh", "행복주택",
        "노숙", "쪽방", "찜질방", "모텔",
        "퇴거", "쫓겨", "이사",
    ]
    if any(kw in text for kw in housing_keywords):
        score += 1

    # 3) 소득·고용 정보
    income_keywords = [
        "소득", "수입", "월급", "급여", "수당",
        "알바", "아르바이트", "파트타임", "근로", "일용직",
        "비정규직", "계약직", "프리랜서",
        "실직", "실업", "백수", "무직",
        "취업", "취준", "구직", "이직", "전직",
        "장기 실업", "경력단절",
    ]
    if any(kw in text for kw in income_keywords):
        score += 1

    # 4) 가족·돌봄·보호자 정보
    family_keywords = [
        "싱글맘", "싱글대디", "한부모", "한 부모",
        "소녀가장", "소년소녀가장", "소녀 가장",
        "혼자 키워", "아이 키워", "아이를 키우", "육아",
        "아이", "자녀", "딸", "아들", "애기",
        "부모님", "부모", "엄마", "아빠",
        "조부모", "할머니", "할아버지",
        "치매", "간병", "돌봄", "보호자", "부양",
        "독거", "혼자 살아요", "혼자 살고",
    ]
    if any(kw in text for kw in family_keywords):
        score += 1

    # 5) 걱정·위기·정서 상태
    concern_keywords = [
        "걱정", "고민", "힘들", "막막", "버티기", "버티기 힘들", "버티기 어려워",
        "부담", "어려움", "어려워요", "위기", "급해", "급한",
        "불안", "우울", "잠이 안 와", "잠이 안와",
        "생활비", "월세", "카드값", "빚", "사채", "연체", "압류",
        "끊길까", "잘릴까", "해고",
    ]
    if any(kw in text for kw in concern_keywords):
        score += 1

    # 6) 건강·의료
    health_keywords = [
        "병원", "병원비", "입원", "수술", "진단",
        "우울증", "불안장애", "공황", "정신과",
    ]
    if any(kw in text for kw in health_keywords):
        score += 1

    # 2개 이상이면 "분야 안내"로 넘어갈 수 있다고 판단
    return score >= 2


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
    🆕 수정: 온보딩 / 상황 요약 / 분야 안내까지만 담당
    카드/제도명/행동 단계는 절대 생성하지 않음
    
    Args:
        user_message: 사용자 입력 메시지
        state: 세션 상태
        skip_onboarding: True면 Onboarding 메시지 생략
        client_type: 클라이언트 타입 ("playmcp" | "chatgpt" | "default")
    
    Returns:
        응답 구조 (온보딩 또는 ①~② 단계만)
    """
    response: Dict[str, Any] = {}
    
    # 0. 먼저 상황 정규화 → user_keywords 채우기
    normalize_result = normalize_user_context(user_message, state)
    has_minimum_info = _has_minimum_context(state)
    
    # 1. ChatGPT 전용 로직은 interaction_count > 0일 때만
    if client_type == "chatgpt" and state.interaction_count > 0:
        if not _should_allow_reorchestrate(user_message, state):
            current_domain = state.chosen_domain or "현재 선택한 분야"
            response["_redirect_to_rank_cards"] = {
                "message": (
                    f"이미 {current_domain} 쪽으로 이야기를 나누고 있어서, "
                    f"이제는 해당 지원을 더 자세히 보는 게 좋아 보여요. "
                    f"'rank_support_cards' 도구를 사용해주세요."
                ),
                "domain": state.chosen_domain,
            }
            return response

        if _is_emotion_only(user_message, state):
            response["_emotion_only"] = {
                "message": (
                    "감정을 표현해주셔서 감사합니다. "
                    "구체적인 지원이 필요하시면 어떤 분야인지 말씀해주세요."
                ),
                "maintain_state": True,
            }
            return response
    
    # (선택) Signal Detection Layer (기존 코드 유지)
    try:
        signal = detect_signal(user_message)
        state.signal_level = signal["signal_level"]
        state.forced_domain = signal.get("forced_domain")
        state.primary_domain = signal.get("primary_domain")
    except Exception:
        state.signal_level = "LEVEL_1"
        state.forced_domain = None
        state.primary_domain = None
    
    # 2. 1턴 처리
    if state.interaction_count == 0 and not skip_onboarding:
        # 2-1) 정보가 충분하지 않으면 → 온보딩
        if not has_minimum_info:
            response["_is_first_response"] = True
            response["onboarding"] = ONBOARDING_MESSAGE
            state.interaction_count += 1
            return response

        # 2-2) 정보가 충분하면 → 바로 상황 요약 + 분야 안내
        # 아래 "공통 ①~② 처리" 로직을 그대로 실행 (return 하지 않음)
    
    # 3. 2턴 이후: 정보 부족 → 추가 온보딩/질문
    if state.interaction_count > 0 and not has_minimum_info:
        response["onboarding"] = (
            "조금만 더 구체적으로 알려주시면,\n"
            "지금 상황에 맞는 지원 분야를 정리해드릴 수 있어요.\n\n"
            + ONBOARDING_MESSAGE
        )
        state.interaction_count += 1
        return response
    
    # 4. 여기까지 왔다는 것은: 정보가 충분하고, 도메인이 아직 확정되지 않은 상태
    #    → ① 상황 요약 + ② 분야 안내만 실행
    
    # 4-1) 상황 요약
    response["step_1_situation_summary"] = {
        "intro": REQUIRED_PHRASES["situation_intro"],
        "summary": normalize_result.get("summary", ""),
        "keywords": normalize_result.get("keywords", []),
    }

    # (선택) 긴급도 평가는 내부용으로만 사용
    urgency_context = {"message": user_message}
    urgency_result = assess_urgency_level(urgency_context, state)
    # 필요하다면 state에 저장만 하고, 출력에는 쓰지 않아도 됩니다.

    # 4-2) 분야 안내
    domains_result = expose_available_domains(state)
    domains = domains_result.get("domains", []) or []

    # (중요) 이 턴에 실제로 보여준 도메인 목록을 state에 저장 (1번/2번 매칭용)
    state.last_shown_domains = domains

    # (선택) 도메인 감지 결과로 "추천 1순위"를 맨 앞으로 정렬
    detected = None
    # detect_domain_from_message 함수가 있다면 사용 (없으면 None)
    # 이 함수는 메뉴 정렬용으로만 사용, 실제 도메인 확정에는 사용하지 않음

    if detected and detected in domains:
        domains.sort(key=lambda d: 0 if d == detected else 1)

    response["step_2_available_domains"] = {
        "intro": REQUIRED_PHRASES["domain_intro"],
        "domains": domains,
        "selection_prompt": (
            "한 번에 다 보려 하면 더 막막해질 수 있으니까,\n"
            "지금 당장 제일 먼저 손대고 싶은 번호 하나만 골라볼게요.\n\n"
            f"👉 1, 2, {len(domains)}번 중에서 "
            "\"이것부터 어떻게든 버텨야겠다\" 싶은 번호 하나만 보내주셔도 괜찮아요."
        ),
    }

    # 카드/행동/제도명은 아직 나오지 않는 상태라는 표시
    response["_domain_not_selected"] = True

    # 🆕 역할 고정 프롬프트 주입 플래그
    if state.interaction_count == 0:
        response["_is_first_response"] = True

    state.interaction_count += 1
    return response


def format_orchestrated_response(orchestrated: Dict[str, Any], state: Optional[SessionState] = None) -> str:
    """
    orchestrate_full_response의 결과를 읽기 쉬운 텍스트로 변환합니다.
    
    Args:
        orchestrated: orchestrate_full_response 반환값
        state: 세션 상태 (선택적, 역할 고정 프롬프트 주입을 위해 사용)
    
    Returns:
        포맷팅된 텍스트 응답
    """
    lines = []
    
    # 🆕 ChatGPT 역할 고정 프롬프트 주입 (세션 최초 호출 시)
    from constants import CHATGPT_ROLE_LOCK_PROMPT
    should_inject_prompt = state and orchestrated.get("_is_first_response", False)
    
    # Onboarding
    if "onboarding" in orchestrated:
        # 🆕 Onboarding에도 역할 고정 프롬프트 주입 (첫 진입이므로)
        if should_inject_prompt:
            lines.append(CHATGPT_ROLE_LOCK_PROMPT)
            lines.append("")
            lines.append("---")
            lines.append("")
        lines.append(orchestrated["onboarding"])
        return "\n".join(lines)
    
    # Onboarding이 아닌 경우에도 역할 고정 프롬프트 주입
    if should_inject_prompt:
        lines.append(CHATGPT_ROLE_LOCK_PROMPT)
        lines.append("")
        lines.append("---")
        lines.append("")
    
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
            # 번호와 함께 표시
            for i, domain in enumerate(step2["domains"], 1):
                lines.append(f"{i}) {domain}")
            lines.append("")
        
        # selection_prompt 추가
        if step2.get("selection_prompt"):
            lines.append(step2["selection_prompt"])
            lines.append("")
        elif step2.get("smart_default"):
            lines.append(step2["smart_default"])
            lines.append("")
    
    # 🆕 도메인 미확정 상태에서는 ③~⑦ 제외
    if orchestrated.get("_domain_not_selected"):
        # ①~②까지만 반환
        return "\n".join(lines)
    
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
    # 🆕 v2: phase 기반 제어 - EXECUTION_READY 단계에서만 표시
    if "step_4_action_steps" in orchestrated and orchestrated["step_4_action_steps"] is not None:
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

