from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from schemas import BenefitCard, RichAttachment, RichResponse, Visual, ProgressBar
from state import SESSION_STORE, SessionState
from constants import ONBOARDING_MESSAGE
from tools.actions import generate_action_steps
from tools.cards import rank_support_cards
from tools.domains import expose_available_domains
from tools.fallback import generate_fallback_paths
from tools.normalize import normalize_user_context
from tools.safety import compose_safe_response
from tools.scoring import get_profile_summary
from tools.urgency import assess_urgency_level
from tools.region import collect_region_context
from tools.policy_trigger import reveal_policy_name_if_triggered
from tools.followup import suggest_followup_options
from tools.orchestrator import orchestrate_full_response, format_orchestrated_response


class ToolCallRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None


class ToolCallResponse(BaseModel):
    session_id: str
    result: Any


app = FastAPI(
    title="Public Support Navigator MCP",
    version="0.50-demo",
    description="판정이 아니라 선택지와 행동 설계에 집중하는 공공 지원 내비게이터 (데모)",
)

# CORS: PlayMCP 등 외부 클라이언트 호환을 위해 최소 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MCP_SPEC = {
    "name": "public-support-mcp",
    "version": "0.50",
    "protocolVersion": "2025-03-26",
    "description": "공공 지원 내비게이터: 판정이 아닌 선택지·행동 설계 중심의 MCP 서버",
    "capabilities": {
        "tools": {}
    },
    "endpoints": {
        "spec": "/mcp",
        "call": "/mcp/call"
    },
    "tools": [
        {
            "name": "orchestrate_full_response",
            "description": "한국 공공 지원(복지, 주거, 의료, 고용 등) 탐색을 위한 통합 상담 도구. 사용자의 경제적 어려움이나 생활 지원 요청에 대해 상황 분석, 지원 분야 안내, 혜택 카드 제안, 실행 계획을 제공합니다.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_message": {
                        "type": "string",
                        "description": "사용자 입력 메시지",
                    },
                    "skip_onboarding": {
                        "type": "boolean",
                        "description": "Onboarding 메시지를 생략할지 여부 (기본값: false)",
                    }
                },
                "required": ["user_message"],
                "additionalProperties": False,
            },
        },
        {
            "name": "normalize_user_context",
            "description": """한국 공공 지원 관련 사용자 발화를 구조화된 상황 정보로 정리.

호출 시점:
- orchestrate_full_response 대신 상황 분석만 먼저 필요할 때
- 사용자가 상황 설명은 했지만 아직 지원 요청은 하지 않았을 때
- 복잡한 상황을 단계적으로 분해하고 싶을 때

예시:
- "30대이고 서울에 살아요. 3년째 백수고 혼자 살아요" (상황만, 요청 없음)
- "결혼 준비 중인데 천안 두정동에 살고 있어요" (배경 정보만)

호출 금지:
- 이미 orchestrate_full_response를 호출한 경우 (중복 방지)
- 공공 지원과 무관한 일상 대화
- 단순 인사나 확인 응답

출력: summary(상황 요약), keywords(키워드 리스트), missing_info(부족한 정보)""",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "사용자 입력 문장",
                    }
                },
                "required": ["message"],
            },
        },
        {
            "name": "assess_urgency_level",
            "description": """공공 지원 상황의 긴급도(1~3) 평가. 내부 로직용, 단독 호출 거의 불필요.

긴급도 기준:
- Level 1 (매우 긴급): 퇴거, 위험, 응급, 폭력 등 즉각 대응 필요
- Level 2 (긴급): 이번 달, 곧, 급한 등 단기 압박
- Level 3 (보통): 일반적인 지원 탐색 상황

호출 시점:
- orchestrate_full_response가 자동으로 처리함
- 개별적으로 긴급도만 판단할 때 (매우 드묾)

대부분의 경우:
- 단독 호출 불필요
- orchestrate_full_response가 자동 감지 및 대응
- 긴급도에 따라 카드 개수와 안전 메시지 자동 조정됨

출력: urgency_level(1, 2, 3)""",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "context": {
                        "type": "object",
                        "description": "message 필드가 포함된 컨텍스트",
                        "properties": {
                            "message": {"type": "string"},
                            "urgency_hint": {"type": "integer"}
                        }
                    }
                },
                "required": ["context"],
            },
        },
        {
            "name": "expose_available_domains",
            "description": """사용자 상황에서 열려 있는 지원 분야 목록 제공 (한국 공공 지원).

핵심 분야: 주거·월세 | 생활 유지 | 의료·돌봄 | 고용·교육 | 심리·정서
확장 분야: 문화·여가 | 평생교육 | 참여·활동 (사용자 명시적 요청 시)

호출 시점:
- orchestrate_full_response가 ②단계에서 자동 포함
- 개별적으로 분야 목록만 보여줄 때 (드묾)
- "어떤 분야가 있어요?" 같은 분야 목록 질문

대부분의 경우:
- 단독 호출 불필요
- orchestrate_full_response 사용 권장
- 구체적인 상담은 orchestrate로 진행

출력: domains(분야 리스트), smart_suggestion(AI 추천 분야)""",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "rank_support_cards",
            "description": """특정 지원 분야의 혜택 카드 2-3개 제공 (한국 공공 지원).

핵심 분야: 주거·월세 | 생활 유지 | 의료·돌봄 | 고용·교육 | 심리·정서
확장 분야: 문화·여가 | 평생교육 | 참여·활동 (사용자 명시적 요청 시)

호출 시점:
- 사용자가 원하는 지원 분야를 이미 명시했을 때
- "더 자세히", "구체적으로", "다른 옵션은?" 요청 시
- 특정 분야에 대한 추가 정보 원할 때

예시:
- "주거 쪽으로 더 자세히 알고 싶어요" → domain: "주거·월세"
- "취업 관련 지원이 궁금해요" → domain: "고용·교육"
- "의료비 부담이 커서 의료 쪽으로" → domain: "의료·돌봄"
- "문화 생활도 하고 싶어요" → domain: "문화·여가"
- "배우고 싶은 게 있어요" → domain: "평생교육"
- "봉사 활동 하고 싶어요" → domain: "참여·활동"

호출 금지:
- 사용자가 아직 분야를 선택하지 않았을 때
- 처음 상담 시작할 때 (orchestrate_full_response 사용)
- 분야가 불명확하거나 여러 개일 때

출력: 각 카드의 "이게 뭐냐면", "왜 지금 맞냐면", "지금 하실 수 있는 말", "어디로", "막히면" 정보""",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "지원 분야 (핵심: 주거·월세, 생활 유지, 의료·돌봄, 고용·교육, 심리·정서 | 확장: 문화·여가, 평생교육, 참여·활동)",
                        "enum": ["주거·월세", "생활 유지", "의료·돌봄", "고용·교육", "심리·정서", "문화·여가", "평생교육", "참여·활동"]
                    }
                },
                "required": [],
            },
        },
        {
            "name": "generate_action_steps",
            "description": """선택한 지원에 대한 실행 계획 제공 (오늘/내일/막히면 3단계).

호출 시점:
- "구체적으로 어떻게 해요?", "방법 알려주세요" 요청
- "오늘 바로 할 수 있는 게 뭐예요?" 질문
- 카드 선택 후 실행 방법이 궁금할 때
- "시작하려면 어떻게 하나요?" 같은 실행 의도

예시:
- "구체적으로 어떻게 시작하나요?"
- "오늘 바로 할 수 있는 일이 뭐예요?"
- "실행 계획을 알려주세요"
- "당장 뭐부터 하면 돼요?"

호출 금지:
- 아직 카드를 선택하지 않았을 때
- orchestrate_full_response가 이미 행동 단계를 포함한 경우
- 단순 정보 질문 단계

출력: today(오늘 할 일), tomorrow(내일까지), fallback(막히면 대안)""",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "generate_fallback_paths",
            "description": """전화 연결 실패, 서류 부족, 자격 애매할 때의 대안 경로 제시 (한국 공공 지원).

호출 시점:
- "전화가 안 돼요", "연결이 안 되는데요" 호소
- "서류가 없어요", "준비가 어려워요" 어려움 표현
- "자격이 안 될 것 같은데", "조건이 애매한데" 걱정
- 실행 중 실제 문제 발생했을 때

예시:
- "전화 연결이 안 되는데 어떻게 해요?"
- "서류 준비가 너무 어려워요"
- "자격이 애매한데 다른 방법은?"
- "담당자가 안 받는데요"

호출 금지:
- 아직 시도하지 않았을 때
- 문제 상황이 실제로 발생하지 않았을 때
- 단순 걱정이나 예상 (실제 막힘 발생 후 호출)

출력: 전화/서류/자격 각 상황별 구체적인 대안 경로""",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "compose_safe_response",
            "description": """응답 마지막에 붙는 감정 안전 메시지 생성 (한국 공공 지원).

호출 시점:
- orchestrate_full_response가 ⑦단계에서 자동으로 포함함
- 개별적으로 감정 지원 메시지만 필요할 때 (매우 드묾)
- 사용자가 불안이나 압박을 표현했을 때

예시 (드묾):
- "무서워요"
- "너무 불안해요"
- "걱정돼요"

대부분의 경우:
- 단독 호출 불필요
- orchestrate_full_response가 자동으로 처리
- 일반적인 상담에서는 호출 금지

출력: 상황에 맞는 감정 안전 메시지 (비판단적, 지지적 톤)""",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "collect_region_context",
            "description": """한국 지역(시/도/군/구) 정보를 수집하여 지역별 지원 안내에 활용.

호출 시점:
- 사용자가 지역 정보를 명시적으로 제공했을 때
- 지역별 지원 차이를 확인해야 할 때
- "OO에 살아요", "OO 거주" 같은 지역 언급

예시:
- "서울 강남구에 살아요"
- "천안 두정동이에요"
- "부산 사상구입니다"
- "경기도 수원시 거주 중이에요"

호출 금지:
- 사용자가 지역 정보를 언급하지 않았을 때
- 이미 지역 정보가 수집되었을 때 (중복 방지)
- 지역과 무관한 일반 질문

출력: collected(수집 성공 여부), region(지역명), message(안내 메시지)""",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "user_input": {
                        "type": "string",
                        "description": "사용자가 제공한 지역 정보 (선택적)",
                    }
                },
                "required": [],
                "additionalProperties": False,
            },
        },
        {
            "name": "reveal_policy_name_if_triggered",
            "description": """사용자가 특정 혜택 카드의 정확한 제도명을 물어볼 때 제도명 공개 (한국 공공 지원).

호출 시점:
- 카드 선택 신호: "1번이 뭐예요?", "첫 번째 할게요", "2번 선택할게요"
- 제도명 직접 질문: "정확한 이름이 뭐예요?", "제도명 알려주세요", "무슨 제도예요?"
- 행동 의도 표현: "어디로 전화해야 해요?", "신청 방법은?", "연락처 알려주세요"

예시:
- "1번이 정확히 뭐예요?"
- "첫 번째 거 선택할게요"
- "이거 정확한 제도 이름 알려주세요"
- "어떻게 신청하나요?"
- "어디로 전화하면 돼요?"

호출 금지:
- 아직 혜택 카드를 제시하지 않았을 때
- 일반적인 지원 정보 질문 (orchestrate_full_response 사용)
- 분야 선택 단계

출력: triggered(트리거 감지 여부), policy_name(제도명), message(안내 메시지)""",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "사용자 입력 메시지",
                    }
                },
                "required": ["message"],
                "additionalProperties": False,
            },
        },
        {
            "name": "suggest_followup_options",
            "description": """현재 선택한 지원 외에 추가로 살펴볼 수 있는 지원 분야 제안 (한국 공공 지원).

호출 시점:
- "또 뭐가 있어요?", "다른 지원도 궁금해요" 질문
- 한 가지 지원을 마무리하고 확장하려 할 때
- "다른 건 없어요?", "추가로 받을 수 있는 거" 같은 추가 탐색 의도

예시:
- "또 받을 수 있는 지원이 있나요?"
- "다른 것도 궁금해요"
- "주거 말고 다른 분야는 뭐가 있어요?"
- "추가로 알아볼 만한 게 있을까요?"

호출 금지:
- 첫 상담 시작 단계 (orchestrate_full_response 사용)
- orchestrate_full_response가 이미 ⑥확장 안내를 포함한 경우
- 아직 하나도 선택하지 않았을 때

출력: followup_domains(추가 분야 리스트), message(안내 메시지)""",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    ],
}


def _normalize(args: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    message = str(args.get("message", "") or "").strip()
    return normalize_user_context(message, state)


def _urgency(args: Dict[str, Any], state: SessionState) -> Dict[str, int]:
    context = args.get("context", {}) or {}
    if not isinstance(context, dict):
        raise HTTPException(status_code=400, detail="context는 object 여야 합니다.")
    return assess_urgency_level(context, state)


def _domains(_: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    return expose_available_domains(state)


def _cards(args: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    # 명시적으로 도메인이 지정되면 chosen_domain에 설정
    domain = args.get("domain")
    if domain:
        state.chosen_domain = domain
    return rank_support_cards(state)


def _actions(_: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    return generate_action_steps(state)


def _fallback(_: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    return generate_fallback_paths(state)


def _safety(_: Dict[str, Any], state: SessionState) -> str:
    return compose_safe_response(state)


def _region(args: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    user_input = args.get("user_input")
    return collect_region_context(state, user_input)


def _policy_trigger(args: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    message = str(args.get("message", "") or "").strip()
    return reveal_policy_name_if_triggered(message, state)


def _followup(_: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    return suggest_followup_options(state)


def _orchestrate(args: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    user_message = str(args.get("user_message", "") or "").strip()
    skip_onboarding = args.get("skip_onboarding", False)
    orchestrated = orchestrate_full_response(user_message, state, skip_onboarding)
    return {
        "orchestrated": orchestrated,
        "formatted_text": format_orchestrated_response(orchestrated)
    }


ToolHandler = Callable[[Dict[str, Any], SessionState], Any]

TOOL_REGISTRY: Dict[str, ToolHandler] = {
    "normalize_user_context": _normalize,
    "assess_urgency_level": _urgency,
    "expose_available_domains": _domains,
    "rank_support_cards": _cards,
    "generate_action_steps": _actions,
    "generate_fallback_paths": _fallback,
    "compose_safe_response": _safety,
    "collect_region_context": _region,
    "reveal_policy_name_if_triggered": _policy_trigger,
    "suggest_followup_options": _followup,
    "orchestrate_full_response": _orchestrate,
}


def _build_content(tool: str | None, arguments: Dict[str, Any], result: Any = None, error: str | None = None) -> List[Dict[str, str]]:
    """도구 실행 결과를 AI가 읽을 수 있는 텍스트로 변환 (레거시 호환)"""
    if error:
        return [{"type": "text", "text": f"도구 실행 중 오류: {error}"}]
    
    if not result:
        return [{"type": "text", "text": "결과 없음"}]
    
    # 각 도구별 결과 포맷팅
    if tool == "normalize_user_context":
        if isinstance(result, dict):
            summary = result.get("summary", "")
            keywords = result.get("keywords", [])
            text = f"{summary}\n\n추출된 키워드: {', '.join(keywords)}" if keywords else summary
            return [{"type": "text", "text": text}]
    
    elif tool == "assess_urgency_level":
        if isinstance(result, dict):
            level = result.get("urgency_level", 3)
            level_text = {1: "매우 긴급", 2: "긴급", 3: "보통"}
            return [{"type": "text", "text": f"긴급도: {level_text.get(level, '보통')} (레벨 {level})"}]
    
    elif tool == "expose_available_domains":
        if isinstance(result, dict):
            domains = result.get("domains", [])
            if domains:
                text = "현재 상황에서 열려 있는 지원 분야:\n" + "\n".join(f"- {d}" for d in domains)
                return [{"type": "text", "text": text}]
    
    elif tool == "rank_support_cards":
        if isinstance(result, dict):
            domain = result.get("domain", "")
            cards = result.get("cards", [])
            if cards:
                # v0.50 엔진 철학 반영: "선택지를 차분하게 정리"
                text = f"지금 상황을 기준으로 보면, {domain} 분야에서 열려 있는 선택지를 정리해봤어요.\n\n"
                
                for i, card in enumerate(cards, 1):
                    # 점수 제거, 카드명만 표시
                    text += f"\n[{card.get('card', '')}]\n\n"
                    
                    if card.get('이게_뭐냐면'):
                        text += f"이게 뭐냐면:\n{card.get('이게_뭐냐면')}\n\n"
                    
                    if card.get('왜_지금_맞냐면'):
                        text += f"왜 지금 맞냐면:\n{card.get('왜_지금_맞냐면')}\n\n"
                    
                    if card.get('지금_하실_수_있는_말'):
                        text += f"지금 하실 수 있는 말:\n\"{card.get('지금_하실_수_있는_말')}\"\n\n"
                    
                    if card.get('where'):
                        text += f"어디로:\n{card.get('where')}\n\n"
                    
                    if card.get('how'):
                        text += f"방법:\n{card.get('how')}\n\n"
                    
                    if card.get('막히면'):
                        text += f"막히면:\n{card.get('막히면')}\n\n"
                
                return [{"type": "text", "text": text}]
    
    elif tool == "generate_action_steps":
        if isinstance(result, dict):
            today = result.get("today", "")
            tomorrow = result.get("tomorrow", "")
            stuck = result.get("stuck", "")
            text = f"【행동 단계】\n\n오늘: {today}\n\n내일: {tomorrow}\n\n막히면: {stuck}"
            return [{"type": "text", "text": text}]
    
    elif tool == "generate_fallback_paths":
        if isinstance(result, dict):
            text = "【대안 경로】\n\n"
            if "call_issue" in result:
                text += f"전화 연결 어려움: {result['call_issue']}\n\n"
            if "docs_issue" in result:
                text += f"서류 준비 어려움: {result['docs_issue']}\n\n"
            if "eligibility_issue" in result:
                text += f"자격 애매함: {result['eligibility_issue']}"
            return [{"type": "text", "text": text}]
    
    elif tool == "compose_safe_response":
        if isinstance(result, str):
            return [{"type": "text", "text": result}]
    
    elif tool == "collect_region_context":
        if isinstance(result, dict):
            status = result.get("status", "")
            message = result.get("message", "")
            if status == "collected":
                region = result.get("region", "")
                text = f"✅ {message}"
            elif status == "already_collected":
                region = result.get("region", "")
                text = f"📍 {message}"
            else:  # requesting
                skip_msg = result.get("skip_message", "")
                text = f"{message}\n\n(참고: {skip_msg})"
            return [{"type": "text", "text": text}]
    
    elif tool == "reveal_policy_name_if_triggered":
        if isinstance(result, dict):
            triggered = result.get("triggered", False)
            if not triggered:
                return [{"type": "text", "text": "제도명 공개 트리거가 감지되지 않았습니다."}]
            
            # result["message"]가 있으면 우선 사용 (이미 포맷팅된 메시지)
            if result.get("message"):
                return [{"type": "text", "text": result["message"]}]
            
            # 없으면 직접 구성
            text = f"⚠️ {result.get('warning_message', '')}\n\n"
            
            policy_info = result.get("policy_info")
            if policy_info:
                card_name = policy_info.get("card_name", "")
                policy_name = policy_info.get("policy_name", "")
                text += f"[{card_name}]은(는) 보통 다음과 같은 제도와 연결되는 경우가 많습니다:\n"
                text += f"  → {policy_name}"
            
            return [{"type": "text", "text": text}]
    
    elif tool == "suggest_followup_options":
        if isinstance(result, dict):
            expansion_msg = result.get("expansion_message", "")
            recommendations = result.get("recommendations", [])
            
            text = f"{expansion_msg}\n\n"
            
            if recommendations:
                text += "예를 들면:\n"
                for rec in recommendations:
                    domain = rec.get("domain", "")
                    reason = rec.get("reason", "")
                    text += f"  • {domain}: {reason}\n"
            
            return [{"type": "text", "text": text}]
    
    elif tool == "orchestrate_full_response":
        if isinstance(result, dict):
            formatted_text = result.get("formatted_text", "")
            if formatted_text:
                return [{"type": "text", "text": formatted_text}]
            else:
                # 포맷팅되지 않았으면 JSON 출력
                import json
                text = json.dumps(result.get("orchestrated", {}), ensure_ascii=False, indent=2)
                return [{"type": "text", "text": text}]
    
    # 기본 폴백: JSON 직렬화
    import json
    try:
        text = json.dumps(result, ensure_ascii=False, indent=2)
        return [{"type": "text", "text": text}]
    except:
        return [{"type": "text", "text": str(result)}]


def _build_rich_response(
    tool: str | None,
    arguments: Dict[str, Any],
    state: SessionState,
    result: Any = None,
    error: str | None = None
) -> RichResponse:
    """🆕 구조화된 Rich Response 생성"""
    if error:
        return RichResponse(
            content=f"도구 실행 중 오류: {error}",
            attachments=[],
            metadata={"error": True}
        )
    
    if not result:
        return RichResponse(
            content="결과 없음",
            attachments=[],
            metadata={}
        )
    
    # 도구별 Rich Response 생성
    if tool == "normalize_user_context":
        summary = result.get("summary", "")
        keywords = result.get("keywords", [])
        
        # 프로파일 정보 첨부
        profile_summary = get_profile_summary(state)
        
        return RichResponse(
            content=f"{summary}\n\n추출된 키워드: {', '.join(keywords)}\n프로파일: {profile_summary}",
            attachments=[
                RichAttachment(
                    type="profile",
                    data={
                        "keywords": keywords,
                        "profile": state.user_profile.model_dump(),
                        "interaction_count": state.interaction_count,
                    }
                )
            ],
            metadata={"tool": tool}
        )
    
    elif tool == "rank_support_cards":
        domain = result.get("domain", "")
        cards = result.get("cards", [])
        
        # 카드 첨부
        card_attachments = []
        for i, card in enumerate(cards, 1):
            score = card.get("eligibility_score", 50)
            
            # 점수에 따른 색상
            if score >= 80:
                color = "#4CAF50"  # 녹색
                badge = "강력 추천"
            elif score >= 60:
                color = "#2196F3"  # 파랑
                badge = "추천"
            else:
                color = "#FF9800"  # 주황
                badge = "참고"
            
            card_attachments.append(
                RichAttachment(
                    type="card",
                    data={
                        "title": card.get("card", ""),
                        "description": card.get("description", ""),
                        "eligibility_score": score,
                        "where": card.get("where"),
                        "how": card.get("how"),
                        "say": card.get("say"),
                        "why": card.get("why"),
                        "visual": {
                            "icon": "💡" if score >= 80 else "📋",
                            "color": color,
                            "badge": badge,
                        }
                    }
                )
            )
        
        content_text = f"【{domain}】 분야에서 {len(cards)}개 혜택을 찾았습니다.\n"
        content_text += f"적합도 점수를 기반으로 정렬했습니다."
        
        return RichResponse(
            content=content_text,
            attachments=card_attachments,
            metadata={"domain": domain, "count": len(cards)}
        )
    
    elif tool == "generate_action_steps":
        today = result.get("today", "")
        tomorrow = result.get("tomorrow", "")
        stuck = result.get("stuck", "")
        
        return RichResponse(
            content="행동 단계를 3단계로 나눴습니다.",
            attachments=[
                RichAttachment(
                    type="action",
                    data={
                        "phase": "today",
                        "title": "오늘 할 일",
                        "description": today,
                        "estimated_time": "30분 이내",
                        "difficulty": "easy",
                    }
                ),
                RichAttachment(
                    type="action",
                    data={
                        "phase": "tomorrow",
                        "title": "내일 할 일",
                        "description": tomorrow,
                        "estimated_time": "1~2시간",
                        "difficulty": "medium",
                    }
                ),
                RichAttachment(
                    type="action",
                    data={
                        "phase": "stuck",
                        "title": "막힐 때",
                        "description": stuck,
                        "estimated_time": "상황별",
                        "difficulty": "medium",
                    }
                ),
            ],
            metadata={"tool": tool}
        )
    
    # 기타 도구는 기존 방식 사용
    legacy_content = _build_content(tool, arguments, result, error)
    return RichResponse(
        content=legacy_content[0]["text"] if legacy_content else "결과 없음",
        attachments=[],
        metadata={"tool": tool, "legacy": True}
    )


@app.api_route("/mcp", methods=["GET", "POST"])
async def get_mcp_spec(_: Dict[str, Any] | None = None) -> JSONResponse:
    return JSONResponse(MCP_SPEC)


@app.get("/")
async def root_get() -> JSONResponse:
    """GET: 기본 서버 정보 반환"""
    return JSONResponse(
        {
            "mcp": True,
            "name": "public-support-mcp",
            "version": "0.50",
            "endpoints": {"spec": "/mcp", "call": "/mcp/call"},
        }
    )


async def _process_mcp_request(payload: dict, request: Request) -> dict:
    """MCP 요청 처리 (공통 로직)"""
    method = payload.get("method")
    request_id = payload.get("id")
    
    print(f"[DEBUG] Parsed - method: {method}, id: {request_id}")
    
    if method == "initialize":
        # MCP initialize 응답
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2025-03-26",
                "serverInfo": {
                    "name": "public-support-mcp",
                    "version": "0.50-demo"
                },
                "capabilities": {
                    "tools": {
                        "listChanged": False
                    },
                    "resources": {}
                }
            }
        }
    elif method == "tools/list":
        # tools 목록 반환
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": MCP_SPEC["tools"]
            }
        }
    elif method == "tools/call":
        # tool 호출 처리
        params = payload.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        # 🆕 Stateless 우선: 세션 ID는 클라이언트가 명시적으로 제공한 경우에만 사용
        session_id = None
        # 1. HTTP 헤더에서 세션 ID 추출 시도
        session_id = request.headers.get("X-Session-ID") or request.headers.get("X-Request-ID")
        # 2. arguments에서 세션 ID 추출 시도
        if not session_id:
            session_id = arguments.get("_session_id") or arguments.get("session_id")
        # 3. 세션이 없으면 새로 생성 (Stateless 권장이지만 호환성을 위해 유지)
        #    단, 세션이 없어도 동작하도록 최소한의 상태만 사용
        
        session_id, state = SESSION_STORE.get(session_id) if session_id else (None, SessionState())
        # 디버깅: 세션 ID 로깅
        print(f"[DEBUG] Session ID: {session_id or 'stateless'}, Tool: {tool_name}")
        
        handler = TOOL_REGISTRY.get(tool_name)
        
        if not handler:
            # 프로토콜 오류: 알 수 없는 도구
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32602,
                    "message": f"Unknown tool: {tool_name}"
                }
            }
        
        try:
            result = handler(arguments, state)
            if session_id:
                SESSION_STORE.set(session_id, state)
            
            # 🆕 Rich Response 생성 (선택적)
            use_rich = arguments.get("_use_rich_response", False)
            if use_rich:
                rich_response = _build_rich_response(tool_name, arguments, state, result=result)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": rich_response.content}],
                        "attachments": [att.model_dump() for att in rich_response.attachments],
                        "metadata": rich_response.metadata,
                        "isError": False,
                    }
                }
            else:
                response_content = _build_content(tool_name, arguments, result=result)
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": response_content,
                        "isError": False,
                    }
                }
                # 세션 ID가 있으면 메타데이터에 포함 (선택적)
                if session_id:
                    response["result"]["_session_id"] = session_id
                return response
        except Exception as exc:
            # 도구 실행 오류: isError 플래그와 함께 반환
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"도구 실행 중 오류: {str(exc)}"}],
                    "isError": True,
                }
            }
    
    # method가 없거나 알 수 없는 요청
    return {
        "mcp": True,
        "name": "public-support-mcp",
        "version": "0.50",
        "endpoints": {"spec": "/mcp", "call": "/mcp/call"},
    }


@app.post("/")
async def root_post(request: Request) -> JSONResponse:
    """POST: JSON-RPC 2.0 기반 MCP 프로토콜 처리 (Streamable HTTP - JSON-RPC over HTTP)"""
    
    # POST body 읽기
    try:
        body = await request.body()
        body_str = body.decode('utf-8') if body else "{}"
        
        # 디버깅: 실제 요청 내용 로깅
        print(f"[DEBUG] POST / received:")
        print(f"  Headers: {dict(request.headers)}")
        print(f"  Body: {body_str[:500]}")  # 처음 500자만
        
        if body:
            payload = json.loads(body_str)
        else:
            payload = {}
    except Exception as e:
        print(f"[ERROR] Body parsing failed: {e}")
        payload = {}
    
    # 요청 처리
    if payload and isinstance(payload, dict):
        response_data = await _process_mcp_request(payload, request)
    else:
        response_data = {
            "mcp": True,
            "name": "public-support-mcp",
            "version": "0.50",
            "endpoints": {"spec": "/mcp", "call": "/mcp/call"},
        }
    
    # JSON-RPC 응답 (Streamable HTTP는 JSON-RPC over HTTP 방식)
    return JSONResponse(response_data)


@app.post("/mcp/call")
async def call_tool(payload: Dict[str, Any]) -> Dict[str, Any]:
    tool = payload.get("tool")
    arguments = payload.get("arguments") or {}
    session_id = payload.get("session_id")
    use_rich = payload.get("use_rich_response", False)  # 🆕 Rich Response 옵션

    if not isinstance(arguments, dict):
        arguments = {}

    # 🆕 Stateless 우선: 세션 ID가 제공된 경우에만 사용
    if session_id:
        session_id, state = SESSION_STORE.get(session_id)
    else:
        state = SessionState()
    
    handler = TOOL_REGISTRY.get(tool)

    if not handler:
        # 알 수 없는 도구
        return JSONResponse({
            "ok": False,
            "tool": tool,
            "arguments": arguments,
            "session_id": session_id,
            "error": f"Unknown tool: {tool}",
            "content": [{"type": "text", "text": f"알 수 없는 도구: {tool}"}],
            "isError": True,
        })

    if handler:
        try:
            result = handler(arguments, state)
            # 세션이 있으면 저장 (Stateless 권장이지만 호환성을 위해 유지)
            if session_id:
                SESSION_STORE.set(session_id, state)
            
            # 🆕 Rich Response 생성
            if use_rich:
                rich_response = _build_rich_response(tool, arguments, state, result=result)
                response = {
                    "ok": True,
                    "tool": tool,
                    "arguments": arguments,
                    "session_id": session_id,
                    "result": result,
                    "content": rich_response.content,
                    "attachments": [att.model_dump() for att in rich_response.attachments],
                    "metadata": rich_response.metadata,
                    "isError": False,
                }
            else:
                response = {
                    "ok": True,
                    "tool": tool,
                    "arguments": arguments,
                    "session_id": session_id,
                    "result": result,
                    "content": _build_content(tool, arguments, result=result),
                    "isError": False,
                }
            return JSONResponse(response)
        except HTTPException as exc:
            # 도구 실행 오류 (입력 검증 등)
            error_detail = getattr(exc, "detail", str(exc))
            response = {
                "ok": False,
                "tool": tool,
                "arguments": arguments,
                "session_id": session_id,
                "error": error_detail,
                "status": getattr(exc, "status_code", 400),
                "content": [{"type": "text", "text": f"입력 오류: {error_detail}"}],
                "isError": True,
            }
            return JSONResponse(response)
        except Exception as exc:  # pragma: no cover - 데모용 방어
            # 도구 실행 오류 (예상치 못한 오류)
            error_detail = f"tool execution failed: {exc}"
            response = {
                "ok": False,
                "tool": tool,
                "arguments": arguments,
                "session_id": session_id,
                "error": error_detail,
                "content": [{"type": "text", "text": f"실행 오류: {error_detail}"}],
                "isError": True,
            }
            return JSONResponse(response)


# ==========================================
# ChatGPT Actions용 OpenAPI 엔드포인트
# ==========================================

def get_openapi_spec() -> Dict[str, Any]:
    """ChatGPT Actions용 OpenAPI 3.0 스펙 생성"""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Public Support Navigator",
            "description": "공공 지원 내비게이터: 판정이 아닌 선택지·행동 설계 중심의 MCP 서버",
            "version": "0.50"
        },
        "servers": [
            {
                "url": "https://public-support-mcp.onrender.com",
                "description": "Production server"
            }
        ],
        "paths": {
            "/orchestrate_full_response": {
                "post": {
                    "summary": "공공 지원 상담 (메인 진입 Tool)",
                    "description": "한국 공공 지원(복지, 주거, 의료, 고용 등) 탐색을 위한 통합 상담 도구. 사용자의 경제적 어려움이나 생활 지원 요청에 대해 상황 분석, 지원 분야 안내, 혜택 카드 제안, 실행 계획을 제공합니다.",
                    "operationId": "orchestrate_full_response",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "user_message": {
                                            "type": "string",
                                            "description": "사용자 입력 메시지"
                                        },
                                        "skip_onboarding": {
                                            "type": "boolean",
                                            "description": "Onboarding 메시지를 생략할지 여부 (기본값: false)",
                                            "default": False
                                        }
                                    },
                                    "required": ["user_message"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "성공",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "orchestrated": {
                                                "type": "object",
                                                "description": "구조화된 상담 응답"
                                            },
                                            "formatted_text": {
                                                "type": "string",
                                                "description": "포맷팅된 텍스트 응답"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/chat": {
                "post": {
                    "summary": "공공 지원 상담 (레거시 엔드포인트)",
                    "description": "사용자의 상황을 분석하고 적절한 지원 옵션을 제안합니다. (내부적으로 orchestrate_full_response 사용)",
                    "operationId": "chat",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "message": {
                                            "type": "string",
                                            "description": "사용자 메시지"
                                        }
                                    },
                                    "required": ["message"]
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "성공",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "response": {
                                                "type": "string",
                                                "description": "공공 지원 상담 응답"
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }


@app.get("/openapi.json")
async def openapi_spec():
    """ChatGPT Actions용 OpenAPI 스펙"""
    return JSONResponse(get_openapi_spec())


@app.post("/orchestrate_full_response")
async def orchestrate_full_response_endpoint(request: Request):
    """ChatGPT Actions용 메인 진입 Tool 엔드포인트"""
    try:
        body = await request.json()
        user_message = body.get("user_message", "")
        skip_onboarding = body.get("skip_onboarding", False)
        
        if not user_message:
            return JSONResponse({
                "error": "user_message 필드가 필요합니다"
            }, status_code=400)
        
        # orchestrate_full_response 사용
        session_id, state = SESSION_STORE.get(None)
        result = orchestrate_full_response(user_message, state, skip_onboarding=skip_onboarding)
        formatted = format_orchestrated_response(result)
        
        return JSONResponse({
            "orchestrated": result.get("orchestrated", {}),
            "formatted_text": formatted
        })
    except Exception as e:
        print(f"[ERROR] /orchestrate_full_response endpoint error: {e}")
        return JSONResponse({
            "error": str(e)
        }, status_code=500)


@app.post("/chat")
async def chat_endpoint(request: Request):
    """ChatGPT Actions 호환 엔드포인트"""
    try:
        body = await request.json()
        user_message = body.get("message", "")
        
        if not user_message:
            return JSONResponse({
                "error": "message 필드가 필요합니다"
            }, status_code=400)
        
        # orchestrate_full_response 사용
        session_id, state = SESSION_STORE.get(None)
        result = orchestrate_full_response(user_message, state, skip_onboarding=False)
        formatted = format_orchestrated_response(result)
        
        return JSONResponse({
            "response": formatted
        })
    except Exception as e:
        print(f"[ERROR] /chat endpoint error: {e}")
        return JSONResponse({
            "error": str(e)
        }, status_code=500)

