from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from state import SESSION_STORE, SessionState
from tools.actions import generate_action_steps
from tools.cards import rank_support_cards
from tools.domains import expose_available_domains
from tools.fallback import generate_fallback_paths
from tools.normalize import normalize_user_context
from tools.safety import compose_safe_response
from tools.urgency import assess_urgency_level


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
        }
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


def _cards(_: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    return rank_support_cards(state)


def _actions(_: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    return generate_action_steps(state)


def _fallback(_: Dict[str, Any], state: SessionState) -> Dict[str, Any]:
    return generate_fallback_paths(state)


def _safety(_: Dict[str, Any], state: SessionState) -> str:
    return compose_safe_response()


ToolHandler = Callable[[Dict[str, Any], SessionState], Any]

TOOL_REGISTRY: Dict[str, ToolHandler] = {
    "normalize_user_context": _normalize,
    "assess_urgency_level": _urgency,
    "expose_available_domains": _domains,
    "rank_support_cards": _cards,
    "generate_action_steps": _actions,
    "generate_fallback_paths": _fallback,
    "compose_safe_response": _safety,
}


def _build_content(tool: str | None, arguments: Dict[str, Any], result: Any = None, error: str | None = None) -> List[Dict[str, str]]:
    message_text: str | None = None
    message_arg = arguments.get("message") if isinstance(arguments, dict) else None

    if tool == "normalize_user_context":
        if isinstance(result, dict) and result.get("summary"):
            message_text = str(result.get("summary"))
        elif message_arg:
            message_text = f"입력하신 내용을 기준으로 상황을 정리했습니다: {message_arg}"

    if not message_text:
        if error:
            message_text = f"tool '{tool}' 처리 중 오류가 있었으나 연결은 유지됩니다: {error}"
        else:
            message_text = f"tool '{tool}'이 정상적으로 처리되었습니다."

    return [{"type": "text", "text": message_text}]


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
                        "tools": {},
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
            
            if handler:
                try:
                    result = handler(arguments, state)
                    SESSION_STORE.set(session_id, state)
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": _build_content(tool_name, arguments, result=result)
                        }
                    })
                except Exception as exc:
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32603,
                            "message": str(exc)
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

    if not isinstance(arguments, dict):
        arguments = {}

    session_id, state = SESSION_STORE.get(session_id)
    handler = TOOL_REGISTRY.get(tool)

    if handler:
        try:
            result = handler(arguments, state)
            SESSION_STORE.set(session_id, state)
            response = {
                "ok": True,
                "tool": tool,
                "arguments": arguments,
                "session_id": session_id,
                "result": result,
                "content": _build_content(tool, arguments, result=result),
            }
            return JSONResponse(response)
        except HTTPException as exc:
            error_detail = getattr(exc, "detail", str(exc))
            response = {
                "ok": False,
                "tool": tool,
                "arguments": arguments,
                "session_id": session_id,
                "error": error_detail,
                "status": getattr(exc, "status_code", 400),
                "content": _build_content(tool, arguments, error=error_detail),
            }
            return JSONResponse(response)
        except Exception as exc:  # pragma: no cover - 데모용 방어
            error_detail = f"tool execution failed: {exc}"
            response = {
                "ok": False,
                "tool": tool,
                "arguments": arguments,
                "session_id": session_id,
                "error": error_detail,
                "content": _build_content(tool, arguments, error=error_detail),
            }
            return JSONResponse(response)

    response = {
        "ok": True,
        "tool": tool,
        "arguments": arguments,
        "session_id": session_id,
        "result": None,
        "content": _build_content(tool, arguments, result=None),
    }
    return JSONResponse(response)

