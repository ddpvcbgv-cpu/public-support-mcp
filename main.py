from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

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
    "version": "0.50-demo",
    "description": "공공 지원 내비게이터: 판정이 아닌 선택지·행동 설계 중심의 MCP 서버 (데모용)",
    "endpoints": {
        "spec": "/mcp",
        "call": "/mcp/call",
        "sse": "/sse",
    },
    "tools": [
        {
            "name": "normalize_user_context",
            "description": "사용자 발화를 상황 정보로 정리합니다",
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
            "description": "문맥을 기반으로 긴급도 레벨(1~3)을 추정합니다",
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
            "description": "현재 상황에서 열려 있는 지원 분야(주거·월세, 생활 유지, 의료·돌봄, 고용·교육, 심리·정서)를 제안합니다",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "rank_support_cards",
            "description": "우선 탐색할 지원 혜택 2~3개를 제안합니다",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "지원 분야 (주거·월세, 생활 유지, 의료·돌봄, 고용·교육, 심리·정서 중 하나)",
                        "enum": ["주거·월세", "생활 유지", "의료·돌봄", "고용·교육", "심리·정서"]
                    }
                },
                "required": [],
            },
        },
        {
            "name": "generate_action_steps",
            "description": "오늘/내일/막히면의 행동 단계를 제공합니다",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "generate_fallback_paths",
            "description": "전화/서류/자격에서 막힐 때의 대안 경로를 제시합니다",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "compose_safe_response",
            "description": "마지막에 붙는 감정 안전 문장을 반환합니다",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "collect_region_context",
            "description": "사용자의 지역 정보(시/군/구)를 부드럽게 수집합니다",
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
            "description": "제도명 공개 트리거를 확인하고, 조건 충족 시 제도명을 공개합니다",
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
            "description": "현재 상황을 기반으로 추가 탐색 가능한 지원 분야를 제안합니다 (⑥ 확장 가능성)",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "orchestrate_full_response",
            "description": "v0.50 엔진 스펙에 따라 ①~⑦ 단계를 자동으로 실행하는 마스터 도구",
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
            "version": "0.50-demo",
            "endpoints": {"spec": "/mcp", "call": "/mcp/call", "sse": "/sse"},
        }
    )


@app.post("/")
async def root_post(request: Request) -> JSONResponse:
    """POST: JSON-RPC 2.0 기반 MCP 프로토콜 처리"""
    
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
    
    # JSON-RPC method 처리
    if payload and isinstance(payload, dict):
        method = payload.get("method")
        request_id = payload.get("id")
        
        print(f"[DEBUG] Parsed - method: {method}, id: {request_id}")
        
        if method == "initialize":
            # MCP initialize 응답
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
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
            })
        elif method == "tools/list":
            # tools 목록 반환
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": MCP_SPEC["tools"]
                }
            })
        elif method == "tools/call":
            # tool 호출 처리 (기존 /mcp/call 로직 재사용)
            params = payload.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            session_id, state = SESSION_STORE.get(None)
            handler = TOOL_REGISTRY.get(tool_name)
            
            if not handler:
                # 프로토콜 오류: 알 수 없는 도구
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": f"Unknown tool: {tool_name}"
                    }
                })
            
            if handler:
                try:
                    result = handler(arguments, state)
                    SESSION_STORE.set(session_id, state)
                    
                    # 🆕 Rich Response 생성 (선택적)
                    use_rich = arguments.get("_use_rich_response", False)
                    if use_rich:
                        rich_response = _build_rich_response(tool_name, arguments, state, result=result)
                        return JSONResponse({
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": [{"type": "text", "text": rich_response.content}],
                                "attachments": [att.model_dump() for att in rich_response.attachments],
                                "metadata": rich_response.metadata,
                                "isError": False,
                            }
                        })
                    else:
                        return JSONResponse({
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": {
                                "content": _build_content(tool_name, arguments, result=result),
                                "isError": False,
                            }
                        })
                except Exception as exc:
                    # 도구 실행 오류: isError 플래그와 함께 반환
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{"type": "text", "text": f"도구 실행 중 오류: {str(exc)}"}],
                            "isError": True,
                        }
                    })
    
    # method가 없거나 알 수 없는 요청: 기본 서버 정보 반환
    return JSONResponse(
        {
            "mcp": True,
            "name": "public-support-mcp",
            "version": "0.50-demo",
            "endpoints": {"spec": "/mcp", "call": "/mcp/call", "sse": "/sse"},
        }
    )


@app.get("/sse")
async def sse_endpoint(request: Request):
    """PlayMCP가 인식하는 SSE 스트림 엔드포인트"""
    
    async def event_generator():
        # 초기 연결 시 MCP 서버 정보 전송
        yield {
            "event": "message",
            "data": json.dumps({
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": MCP_SPEC
            })
        }
        
        # 연결 유지 (클라이언트 연결 끊기면 종료)
        try:
            while True:
                if await request.is_disconnected():
                    break
                # 주기적으로 heartbeat 전송
                yield {
                    "event": "ping",
                    "data": json.dumps({"status": "alive"})
                }
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass
    
    return EventSourceResponse(event_generator())


@app.post("/mcp/call")
async def call_tool(payload: Dict[str, Any]) -> Dict[str, Any]:
    tool = payload.get("tool")
    arguments = payload.get("arguments") or {}
    session_id = payload.get("session_id")
    use_rich = payload.get("use_rich_response", False)  # 🆕 Rich Response 옵션

    if not isinstance(arguments, dict):
        arguments = {}

    session_id, state = SESSION_STORE.get(session_id)
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

